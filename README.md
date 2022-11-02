# Task Analytics

The main goal for this tool is to help you visualize, analyze and get insights about your task data.

You can access the demo in [task-analytics.marianoog.com](https://task-analytics.marianoog.com/).

## How to run this tool locally

1. Clone the repository `git clone https://github.com/MarianoOG/Todoist-Analytics.git`

2. Create a virtual environment `python -m venv venv`

3. Install dependencies `pip install -r requirements.txt`

4. Create an app in your todoist [App Management](https://developer.todoist.com/appconsole.html) page.

5. Create the environment variables with your app client_id and client_secret.

6. Run the streamlit app `streamlit run 🏠_Homepage.py --server.port 8080`

* Alternatively you can also use docker, just remember to use -p 8080:8080 and declare the environment variables
