import time
import requests
import pandas as pd
from datetime import timedelta


class DataCollector:
    def __init__(self, token):
        self.token = token
        self.sync_token = "*"
        self._sync()
        self.current_offset = 0
        self.tasks = pd.DataFrame()
        self._collect_all_completed_tasks()
        self._preprocess_data()

    def _sync(self):
        url = "https://api.todoist.com/sync/v9/sync"

        headers = {"Accept": "application/json",
                   "Authorization": f"Bearer {self.token}"}
        params = {"sync_token": self.sync_token,
                  "resource_types": '["user", "projects", "labels", "items"]'}

        resp = requests.get(url, headers=headers, params=params)

        if resp.status_code != 200:
            print("There was a problem during sync.")
            return

        data = resp.json()

        self.user = data["user"]
        self.projects = data["projects"]
        self.labels = data["labels"]
        self.items = data["items"]
        self.sync_token = data["sync_token"]

    def _collect_all_completed_tasks(self, limit=10000):
        collecting = True
        old_num_items = 0

        while collecting:
            self._collect_completed_tasks(limit=200, offset=self.current_offset)
            current_num_items = self.tasks.shape[0]
            if current_num_items != old_num_items and current_num_items < limit:
                old_num_items = current_num_items
                self.current_offset += 200
            else:
                self.current_offset = current_num_items
                collecting = False

    def _collect_completed_tasks(self, limit, offset):
        url = 'https://api.todoist.com/sync/v9/completed/get_all'
        headers = {"Accept": "application/json",
                   "Authorization": f"Bearer {self.token}"}
        params = {"limit": limit, "offset": offset}
        resp = requests.get(url, headers=headers, params=params)

        if resp.status_code != 200:
            time.sleep(1)
            self._collect_completed_tasks(limit, offset)
        else:
            data = resp.json()
            if len(data["items"]) != 0:
                items = pd.DataFrame(data["items"])
                self.tasks = pd.concat([self.tasks, items])

    def _preprocess_data(self):
        # Projects
        projects = pd.DataFrame()
        projects["project_id"] = [p["id"] for p in self.projects]
        projects["project_name"] = [p["name"] for p in self.projects]
        projects["color"] = [p["color"] for p in self.projects]

        # Labels
        labels = dict()
        for p in self.labels:
            labels[p["id"]] = p["name"]

        # Active tasks
        active_tasks = pd.DataFrame()
        active_tasks["task_id"] = [p["id"] for p in self.items]
        active_tasks["content"] = [p["content"] for p in self.items]
        active_tasks["priority"] = [p["priority"] for p in self.items]
        active_tasks["project_id"] = [p["project_id"] for p in self.items]
        active_tasks["labels"] = [[label for label in p["labels"]] for p in self.items]
        active_tasks["added_at"] = [p["added_at"] for p in self.items]
        active_tasks["due_date"] = [p["due"]["date"] if p["due"] else None for p in self.items]
        active_tasks["recurring"] = [p["due"]["is_recurring"] if p["due"] else None for p in self.items]
        active_tasks = active_tasks.merge(projects[["project_id", "project_name", "color"]],
                                          how="left",
                                          on="project_id")
        active_tasks.drop(["project_id"], axis=1, inplace=True)

        # completed_tasks
        print(self.tasks.columns)
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
