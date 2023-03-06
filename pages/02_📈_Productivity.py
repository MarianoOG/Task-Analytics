import pandas as pd
from datetime import date
import streamlit as st
from src.utils import is_data_ready
from src.plots import plot_with_average, histogram
from prophet import Prophet
from prophet.plot import add_changepoints_to_plot


def render():
    # Title
    st.title("Productivity")
    st.sidebar.caption("Change your day and week goals in the [productivity settings]("
                       "https://todoist.com/app/settings/productivity) inside of todoist.")

    # Get all tasks
    completed_tasks = st.session_state["tasks"].copy().dropna(subset=["completed_at"])
    completed_tasks["week"] = completed_tasks["completed_year"].astype(str) + "-S" + \
        completed_tasks["completed_week"].map(lambda x: "{:02d}".format(x))

    # Get count of completed tasks per day and week
    completed_tasks_per_day = completed_tasks["task_id"].groupby(by=completed_tasks["completed_at"].dt.date)\
                                                        .count().rename("count")
    completed_tasks_per_week = completed_tasks["task_id"].groupby(by=completed_tasks["week"]).count().rename("count")

    # Calculate Velocity
    day_velocity = completed_tasks_per_day.ewm(span=7).mean()[-2]
    week_velocity = completed_tasks_per_week.ewm(span=13).mean()[-2]

    # Create forecast over the next week of the data
    data = completed_tasks_per_day.copy().reset_index()
    data = data.rename(columns={"completed_at": "ds", "count": "y"})
    m = Prophet(changepoint_prior_scale=2.0)
    m.fit(data)
    future = m.make_future_dataframe(periods=7)
    forecast = m.predict(future)

    # Calculate recommended goals based on predictions
    prediction = forecast[["ds", "trend", "yhat"]].tail(7)
    prediction["yhat"][prediction["yhat"] <= 0.0] = prediction["trend"]
    prediction["day_of_the_week"] = prediction["ds"].apply(lambda x: x.weekday() + 1)
    recommended_daily_goal = prediction[prediction["day_of_the_week"].apply(
                                lambda x: x not in st.session_state["user"]["days_off"])]["yhat"].mean()
    recommended_weekly_goal = prediction["yhat"].sum()

    # Get goals per day and week
    daily_goal = st.session_state["user"].get("daily_goal", 0)
    weekly_goal = st.session_state["user"].get("weekly_goal", 0)

    # Get age of active tasks
    active_tasks = st.session_state["tasks"].copy()
    active_tasks = active_tasks[active_tasks["added_at"].apply(lambda x: not pd.isnull(x))]
    active_tasks = active_tasks[active_tasks["due_date"].apply(lambda x: pd.isnull(x))]
    active_tasks = active_tasks[active_tasks["recurring"].apply(lambda x: not x)]
    active_tasks["age_in_days"] = (date.today() - active_tasks["added_at"].dt.date).dt.days

    # Daily goals, velocity and recommendation
    col1, col2, col3 = st.columns(3)
    col1.metric("Daily Goal",
                "{} tasks".format(daily_goal),
                help="The goal you set for yourself in todoist.")
    col2.metric("Actual Velocity (tasks/day)",
                "{}".format(round(day_velocity, 1)),
                help="Calculated using Exponential Moving Average on 7 days (EMA7) for yesterday.")
    col3.metric("Recommended Goal",
                "{} tasks".format(round(recommended_daily_goal)),
                help="Calculated using ML forecast over the next week (excludes days off)")
    day_fig, _ = plot_with_average(completed_tasks_per_day,
                                   x_label="Date",
                                   y_label="# Tasks",
                                   labelrotation=30,
                                   x_tick_interval=30)
    st.pyplot(day_fig)

    # Plot forecast
    with st.expander("Trend Line Analysis"):
        forecast_fig = m.plot(forecast)
        add_changepoints_to_plot(forecast_fig.gca(), m, forecast)
        st.pyplot(forecast_fig)

    # Weekly goals, velocity and recommendation
    col1, col2, col3 = st.columns(3)
    col1.metric("Weekly Goal",
                "{} tasks".format(weekly_goal),
                help="The goal you set for yourself in todoist.")
    col2.metric("Actual Velocity (tasks/week)",
                "{}".format(round(week_velocity, 1)),
                help="Calculated using Exponential Moving Average on 13 weeks (EMA13) for last week.")
    col3.metric("Recommended Goal",
                "{} tasks".format(round(recommended_weekly_goal)),
                help="Calculated using ML forecast over the next week")
    week_fig, _ = plot_with_average(completed_tasks_per_week,
                                    x_label="Week",
                                    y_label="# Tasks",
                                    labelrotation=30,
                                    x_tick_interval=5)
    st.pyplot(week_fig)

    # WIP, age, and lead time
    col1, col2, col3 = st.columns(3)
    col1.metric("Work In Progress",
                "{} tasks".format(active_tasks.shape[0]),
                help="Current amount of active tasks.")
    col2.metric("Average Age",
                "{} days".format(round(active_tasks["age_in_days"].mean(), 1)),
                help="Average age since tasks were created.")
    col3.metric("Lead time",
                "{} days".format(round(active_tasks.shape[0] / day_velocity, 1)),
                help="Expected amount of time to complete a task once its created.")
    fig, _ = histogram(active_tasks["age_in_days"])
    st.pyplot(fig)

    # Oldest task list
    with st.expander("Oldest tasks"):
        st.write("")
        oldest = active_tasks.sort_values("age_in_days", ascending=False).head(10)
        table_str = "| Added Date | Project | Labels | Content | URL |\n"
        table_str += "|----|----|----|----|----|\n"
        for added, project, labels, task, task_id in zip(oldest["added_at"], oldest["project_name"], oldest["labels"],
                                                         oldest["content"], oldest["task_id"]):
            table_str += f"| **{added.date()}** | {project} | {', '.join(labels)} | {task} | " \
                         f"*[open in todoist](https://todoist.com/app/task/{task_id})* | \n"
        st.markdown(table_str)
        st.write("")


if __name__ == "__main__":
    if is_data_ready():
        render()
