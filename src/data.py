import asyncio
import requests
import pandas as pd
from datetime import timedelta


class DataCollector:
    def __init__(self, token):
        self.token = token
        self.current_offset = 0
        self.items = pd.DataFrame()
        items, projects = self._load_current_tasks()
        self._preprocess_data(items, projects)

    def _load_current_tasks(self):
        # API request
        url = "https://api.todoist.com/sync/v9/sync"
        headers = {"Accept": "application/json",
                   "Authorization": f"Bearer {self.token}"}
        params = {"sync_token": "*",
                  "resource_types": '["user", "projects", "items"]'}
        resp = requests.get(url, headers=headers, params=params)

        # Handle error
        if resp.status_code != 200:
            print(f"There was a problem during sync with status code {resp.status_code}.")
            return

        # Parse response
        data = resp.json()
        self.user = data["user"]
        return data["items"], data["projects"]

    def collect_more_tasks(self):
        asyncio.run(self._collect_all_completed_tasks())

    async def _collect_all_completed_tasks(self, max_items: int = 2000):
        step = 200
        tasks = [self._collect_completed_tasks_async(step, i * step + self.current_offset)
                 for i in range(int(max_items/step))]
        self.current_offset += max_items

        # Wait for next result and preprocess data if available
        for task in asyncio.as_completed(tasks):
            result = await task
            if not result:
                continue
            items, projects = result
            self._preprocess_data(items, projects)

    def _collect_completed_tasks(self, limit, offset):
        # API request
        url = 'https://api.todoist.com/sync/v9/completed/get_all'
        headers = {"Accept": "application/json",
                   "Authorization": f"Bearer {self.token}"}
        params = {"limit": limit, "offset": offset, "annotate_notes": False}
        resp = requests.get(url, headers=headers, params=params)

        # Handle error
        if resp.status_code != 200:
            print("There was a problem during collection.\n",
                  f"\tStatus code: {resp.status_code}\n",
                  f"\tLimit: {limit}\n",
                  f"\tOffset: {offset}")
            return

        # Return data
        data = resp.json()
        return data["items"], data["projects"]

    async def _collect_completed_tasks_async(self, limit, offset):
        return await asyncio.get_running_loop().run_in_executor(None, self._collect_completed_tasks, limit, offset)

    def _preprocess_data(self, items, projects):
        # Verify there's at least one new task
        if len(items) == 0:
            return

        # Format Projects
        if type(projects) == list:
            projects = pd.DataFrame(projects).rename(columns={"id": "project_id", "name": "project_name"})
        else:
            projects = pd.DataFrame(projects.values(), index=projects.keys()).reset_index()
            projects = projects.rename(columns={"index": "project_id"})
            projects["project_name"] = projects.apply(lambda x: x["project_id"] if x["name"] == '' else x["name"],
                                                      axis=1)
        projects = projects[["project_id", "project_name", "color"]]

        # Transform items data into a DataFrame
        items = pd.DataFrame(items)

        # Use id as tasks_id if not provided
        if "task_id" not in items.columns.values.tolist():
            items = items.rename(columns={"id": "task_id"})

        # Format due_date and recurring data (or enhance it if possible)
        if "due" in items.columns.values.tolist():
            items["due_date"] = items["due"].apply(lambda x: x["date"] if x else None)
            items["recurring"] = items["due"].apply(lambda x: x["is_recurring"] if x else False)
        else:
            items = items.merge(self.items[["task_id", "recurring"]], how="left", on="task_id")

        # Set default priority to 0 if not provided then, add format
        if "priority" not in items.columns.values.tolist():
            items["priority"] = 0
        items["priority"] = items["priority"].apply(lambda x: "Priority {}".format(x))

        # Create missing columns when not present
        column_names = ["task_id", "content", "priority", "project_id", "recurring",
                        "labels", "added_at", "due_date", "completed_at"]
        for column in column_names:
            if column not in items.columns.values.tolist():
                items[column] = None

        # Simplify columns and merge items with projects
        items = items[column_names]
        items = items.merge(projects, how="left", on="project_id")
        items.drop(["project_id"], axis=1, inplace=True)

        # Format dates using timezone
        timezone = self.user["tz_info"]["timezone"]
        items["completed_at"] = pd.to_datetime(items["completed_at"], utc=True).map(lambda x: x.tz_convert(timezone))
        items["added_at"] = pd.to_datetime(items["added_at"], utc=True).map(lambda x: x.tz_convert(timezone))
        items["due_date"] = pd.to_datetime(items["due_date"], utc=True).map(lambda x: x.tz_convert(timezone))

        # Enhance the dataframe with year, quarter, month, week, day
        start_day = 8 - self.user["start_day"]
        items["completed_year"] = items["completed_at"].dt.year
        items["completed_quarter"] = items["completed_at"].dt.quarter
        items["completed_month"] = items["completed_at"].dt.month
        items["completed_week"] = items["completed_at"].dt.date.map(lambda x: None if pd.isnull(x) else (x + timedelta(
            days=start_day)).isocalendar()[1])
        items["completed_day"] = items['completed_at'].dt.day
        items["due_year"] = items["due_date"].dt.year
        items["due_quarter"] = items["due_date"].dt.quarter
        items["due_month"] = items["due_date"].dt.month
        items["due_week"] = items["due_date"].dt.date.map(lambda x: None if pd.isnull(x) else (x + timedelta(
            days=start_day)).isocalendar()[1])
        items["due_day"] = items['due_date'].dt.day

        # Combine all tasks in one dataframe and format columns
        self.items = pd.concat([items, self.items], axis=0, ignore_index=True)
        self.items["recurring"] = self.items["recurring"].astype("bool")
        for column in ["task_id", "content", "project_name"]:
            self.items[column] = self.items[column].astype("string")
        for column in ["priority", "project_name", "color"]:
            self.items[column] = self.items[column].astype("category")
        for column in ["completed_year", "completed_quarter", "completed_month", "completed_week", "completed_day",
                       "due_year", "due_quarter", "due_month", "due_week", "due_day"]:
            self.items[column] = self.items[column].astype("Int64")
