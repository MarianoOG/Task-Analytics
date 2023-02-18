import json
import asyncio
import requests
import pandas as pd
from datetime import timedelta


class DataCollector:
    def __init__(self, token):
        self.token = token
        self.sync_token = "*"
        self.collecting = True
        self.current_offset = 0
        self._sync()

    def collect_batch_of_completed_tasks(self):
        asyncio.run(self._collect_all_completed_tasks())

    def _sync(self):
        # API request
        url = "https://api.todoist.com/sync/v9/sync"
        headers = {"Accept": "application/json",
                   "Authorization": f"Bearer {self.token}"}
        params = {"sync_token": self.sync_token,
                  "resource_types": '["user", "projects", "items"]'}
        resp = requests.get(url, headers=headers, params=params)

        # Response error
        if resp.status_code != 200:
            print("There was a problem during sync.")
            self.collecting = False
            return

        # Parse response
        data = resp.json()

        self.sync_token = data["sync_token"]
        self.user = data["user"]
        self.projects = pd.DataFrame(data["projects"]).rename(columns={"id": "project_id", "name": "project_name"})
        self.projects = self.projects[["project_id", "project_name", "color"]]
        self.tasks = pd.DataFrame(data["items"]).rename(columns={"id": "task_id"})
        self.tasks["due_date"] = self.tasks["due"].apply(lambda x: x["due"]["date"])
        self.tasks["recurring"] = self.tasks.apply(lambda x: x["due"]["is_recurring"])
        self.tasks = self.tasks[["task_id", "content", "priority", "project_id", "added_at", "due_date", "recurring"]]
        print(self.tasks.columns)
        print(self.tasks)

    async def _collect_all_completed_tasks(self):
        max_items = 2000
        step = 200
        tasks = [self._collect_completed_tasks_async(step, i * step + self.current_offset)
                 for i in range(int(max_items/step))]
        self.current_offset += max_items

        for task in asyncio.as_completed(tasks):
            result = await task
            if result:
                items, projects = result
                self._preprocess_data(items, projects)

    def _collect_completed_tasks(self, limit, offset):
        url = 'https://api.todoist.com/sync/v9/completed/get_all'
        headers = {"Accept": "application/json",
                   "Authorization": f"Bearer {self.token}"}
        params = {"limit": limit, "offset": offset, "annotate_notes": False}
        resp = requests.get(url, headers=headers, params=params)
        print("offset", offset, resp.status_code)

        # Return data
        if resp.status_code == 200:
            data = resp.json()
            if len(data["items"]) != 0:
                return data["items"], data["projects"]

        return None

    async def _collect_completed_tasks_async(self, limit, offset):
        return await asyncio.get_running_loop().run_in_executor(None, self._collect_completed_tasks, limit, offset)

    def _preprocess_data(self, tasks, projects):
        # Projects
        projects["project_id"] = [p["id"] for p in projects]
        projects["project_name"] = [p["name"] for p in projects]
        projects["color"] = [p["color"] for p in projects]

        # Active tasks
        active_tasks = pd.DataFrame()
        active_tasks["task_id"] = [p["id"] for p in tasks]
        active_tasks["content"] = [p["content"] for p in tasks]
        active_tasks["priority"] = [p["priority"] for p in tasks]
        active_tasks["project_id"] = [p["project_id"] for p in tasks]
        active_tasks["added_at"] = [p["added_at"] for p in tasks]
        active_tasks["due_date"] = [p["due"]["date"] if p["due"] else None for p in tasks]
        active_tasks["recurring"] = [p["due"]["is_recurring"] if p["due"] else None for p in tasks]
        active_tasks = active_tasks.merge(projects[["project_id", "project_name", "color"]],
                                          how="left",
                                          on="project_id")
        active_tasks.drop(["project_id"], axis=1, inplace=True)

        # completed_tasks
        self.tasks["priority"] = 0
        self.tasks = self.tasks.merge(projects[["project_id", "project_name", "color"]],
                                      how="left",
                                      on="project_id")
        self.tasks = self.tasks.merge(active_tasks[["task_id", "recurring"]],
                                      how="left",
                                      on="task_id")

        # Combine all tasks in one dataframe
        self.tasks = pd.concat([active_tasks, self.tasks], axis=0, ignore_index=True)
        self.tasks.drop(["meta_data", "user_id", "id", "project_id"], axis=1, inplace=True)
        self.tasks["project_name"] = self.tasks["project_name"].fillna("<No project data>")
        self.tasks["priority"] = self.tasks["priority"].apply(lambda x: "Priority {}".format(x))

        # Format dates using timezone
        timezone = self.user["tz_info"]["timezone"]
        self.tasks["completed_at"] = pd.to_datetime(self.tasks["completed_at"]).map(
            lambda x: x.tz_convert(timezone))
        self.tasks["added_at"] = pd.to_datetime(self.tasks["added_at"]).map(
            lambda x: x.tz_convert(timezone))
        self.tasks["due_date"] = pd.to_datetime(self.tasks["due_date"], utc=True).map(
            lambda x: x.tz_convert(timezone))

        # Enhance the dataframe with year, quarter, month, week, day
        self.tasks["year"] = self.tasks["completed_at"].dt.year
        self.tasks["quarter"] = self.tasks["completed_at"].dt.quarter
        self.tasks["month"] = self.tasks["completed_at"].dt.month
        start_day = 8 - self.user["start_day"]
        self.tasks["week"] = self.tasks["completed_at"].dt.date.map(lambda x: None if pd.isnull(x) else (x +
                                                                    timedelta(days=start_day)).isocalendar()[1])
        self.tasks["day"] = self.tasks['completed_at'].dt.day

        # Format other columns
        self.tasks["priority"] = self.tasks["priority"].astype("category")
        self.tasks["recurring"] = self.tasks["recurring"].astype("bool")
        self.tasks["project_name"] = self.tasks["project_name"].astype("category")
        self.tasks["color"] = self.tasks["color"].astype("category")
        self.tasks["year"] = self.tasks["year"].astype("Int64")
        self.tasks["quarter"] = self.tasks["quarter"].astype("Int64")
        self.tasks["month"] = self.tasks["month"].astype("Int64")
        self.tasks["week"] = self.tasks["week"].astype("Int64")
        self.tasks["day"] = self.tasks["day"].astype("Int64")
