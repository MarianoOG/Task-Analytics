import streamlit as st
from datetime import date, timedelta
from src.utils import is_data_ready
from src.plots import plot_with_average


def habits_and_goals_metrics(goal, actual, habits):
    col1, col2, col3 = st.columns(3)
    habits_delta = (habits / actual) / goal - 1 if actual > 0 and goal > 0 else 0.0
    non_habits_delta = ((actual-habits) / actual) / (1-goal) - 1 if actual > 0 and (1-goal) > 0 else 0.0
    score = 1 + non_habits_delta if habits_delta > 0.0 else habits_delta + 1
    col1.metric("Completed tasks", actual, delta_color="off",
                delta="{:.0%}".format(score))
    col2.metric("Habits", habits,
                delta="{:.0%}".format(habits_delta))
    col3.metric("Non-Habits", actual-habits,
                delta="{:.0%}".format(non_habits_delta))


def render():
    ################################
    #             DATA             #
    ################################

    # Get all tasks
    tasks = st.session_state["tasks"].copy()
    tasks = tasks[["task_id", "content", "project_name", "completed_at"]].dropna(subset=["completed_at"])

    ################################
    #           SIDEBAR            #
    ################################

    # Sidebar notes and controls
    st.sidebar.caption("Habits are recurring tasks completed at least twice.")
    habit_percentage = st.sidebar.slider(label="Percentage slider",
                                         min_value=1,
                                         max_value=99,
                                         value=30,
                                         format="%i%%") / 100.0
    selected_date = st.sidebar.date_input("Date",
                                          date.today(),
                                          min_value=min(tasks["completed_at"].to_list()),
                                          max_value=max(tasks["completed_at"].to_list()))

    # Unpack date
    year = selected_date.year
    month = selected_date.month
    quarter = (month - 1) // 3 + 1
    day = selected_date.day
    start_day = 8 - st.session_state["user"]["start_day"]
    week = (date(year, month, day) + timedelta(days=start_day)).isocalendar()[1]

    ################################
    #         FILTER DATA          #
    ################################

    # Tasks per period of time
    tasks_of_year = tasks[tasks["completed_at"].dt.year == year]
    tasks_of_quarter = tasks_of_year[tasks_of_year["completed_at"].dt.quarter == quarter]
    tasks_of_month = tasks_of_quarter[tasks_of_quarter["completed_at"].dt.month == month]
    tasks_of_week = tasks_of_year[(tasks_of_year["completed_at"] +
                                   timedelta(days=start_day)).dt.isocalendar().week == week]

    # Filter for habits
    habits = tasks[tasks.duplicated(subset=["task_id"], keep=False)]
    habits_of_year = habits[habits["completed_at"].dt.year == year]
    habits_of_quarter = habits_of_year[habits_of_year["completed_at"].dt.quarter == quarter]
    habits_of_month = habits_of_quarter[habits_of_quarter["completed_at"].dt.month == month]
    habits_of_week = habits_of_year[(habits_of_year["completed_at"] +
                                     timedelta(days=start_day)).dt.isocalendar().week == week]
    # Get the number of aggregated tasks per day
    counts_of_year_per_day = tasks_of_year["task_id"].groupby(by=tasks_of_year['completed_at'].dt.date).count()
    counts_of_quarter_per_day = counts_of_year_per_day[tasks_of_quarter['completed_at'].dt.date]
    counts_of_month_per_day = counts_of_quarter_per_day[tasks_of_month['completed_at'].dt.date]
    counts_of_week_per_day = counts_of_year_per_day[tasks_of_week['completed_at'].dt.date]

    # Get the number of aggregated tasks per month
    month_names = ['January', 'February', 'March', 'April', 'May', 'June',
                   'July', 'August', 'September', 'October', 'November', 'December']
    counts_of_year_per_month = tasks_of_year["task_id"].groupby(by=tasks_of_year['completed_at'].dt.month).count()
    counts_of_quarter_per_month = counts_of_year_per_month[tasks_of_quarter['completed_at'].dt.month]
    counts_of_year_per_month.set_axis([month_names[i - 1] for i in counts_of_year_per_month.index], inplace=True)
    counts_of_quarter_per_month.set_axis([month_names[i - 1] for i in counts_of_quarter_per_month.index], inplace=True)

    ################################
    #        MAIN DASHBOARD        #
    ################################

    # Title
    st.title("Habits")

    # Week category pie and plot with average
    st.header("Week")
    habits_and_goals_metrics(habit_percentage, tasks_of_week.shape[0], habits_of_week.shape[0])
    fig1, _ = plot_with_average(counts_of_week_per_day,
                                x_label="Day",
                                y_label="# Tasks",
                                labelrotation=30,
                                x_tick_interval=1)
    st.pyplot(fig1)

    # Month category pie and plot with average
    st.header("Month")
    habits_and_goals_metrics(habit_percentage, tasks_of_month.shape[0], habits_of_month.shape[0])
    fig2, _ = plot_with_average(counts_of_month_per_day,
                                x_label="Day",
                                y_label="# Tasks",
                                labelrotation=30,
                                x_tick_interval=2)
    st.pyplot(fig2)

    # Quarter category pie and plot with average
    st.header("Quarter")
    habits_and_goals_metrics(habit_percentage, tasks_of_quarter.shape[0], habits_of_quarter.shape[0])
    fig3, _ = plot_with_average(counts_of_quarter_per_day,
                                x_label="Day",
                                y_label="# Tasks",
                                labelrotation=30)
    st.pyplot(fig3)


if __name__ == "__main__":
    if is_data_ready():
        render()
