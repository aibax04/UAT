 Crawl AI – Autonomous UX Testing Agent

Crawl AI is an AI-powered autonomous UX Testing Agent that automatically crawls your web application, evaluates UI/UX quality, identifies friction points, and generates actionable design insights—just like a real human UX researcher.

Built using LLMs, human-behavior simulation, heuristic analysis, visual evaluation, and agentic workflows, Crawl AI helps product teams speed up usability testing and ship better user experiences.

 Key Features

Autonomous UI Crawling
Automatically explores your website like a first-time user.

Human-Like UX Judgement
Uses psychology-driven prompting to evaluate:

Visual hierarchy

Confusion points

Friction

Cognitive load

Emotional response

Actionable UX Recommendations
Generates prioritized suggestions based on UX heuristics (Nielsen, Gestalt, Hick’s Law, Fitts’s Law).

Persona-Based Testing
Simulates different user types:

Novice user

Distracted user

Rushed user

Frustrated user

AI-Driven Usability Reports
Produces structured UX reviews, heatmap hypotheses, and fixable design improvements.

Integrates With CI/CD
Run automated UX audits on every deployment.

 How It Works

Crawl Agent loads the webpage and discovers clickable elements & user flows.

Interaction Agent performs realistic actions (clicks, inputs, scrolls).

UX Critic Agent evaluates the experience using human-like reasoning.

Report Generator creates:

UX issues

Severity scores

Recommendations

Screenshots & insights

 Project Structure
crawl-ai/
│── graph.py        # Main LangGraph orchestration logic
│── tools.py        # Browser automation, crawling tools, utility functions
│── prompt.py       # Human-like UX critic system prompts
│── requirements.txt
│── README.md
│── /reports        # Generated UX reports
│── /screenshots    # Screenshots captured during crawling

 Tech Stack

Python / LangChain / LangGraph

Playwright / Selenium

Gemini / Groq / Claude (pluggable LLMs)

Heuristic UX evaluation frameworks

Multi-agent reasoning

 Getting Started
1. Clone Repository
git clone https://github.com/your-username/crawl-ai.git
cd crawl-ai

2. Create & Activate Virtual Environment
python -m venv venv
source venv/bin/activate     # Mac/Linux
venv\Scripts\activate        # Windows

3. Install Dependencies
pip install -r requirements.txt

4. Run the Agent
python graph.py

 Example Output

Crawl AI generates:

A list of UX problems with severity

Page-flow insights

Recommended UI improvements

Suggested microcopy revisions

Persona-based usability breakdown

 Use Cases

UX teams wanting faster audits

Product teams shipping weekly sprints

Solo founders needing quick UX validation

QA teams adding usability checks to pipelines

Agencies auditing client websites

 Competitors in the Market

UserTesting

Maze

UXtweak

Synthetic Users

Odaptos

Crawl AI is different because it focuses on autonomous UX auditing with human-like intelligence, not just analytics or surveys.

 Contributing

Contributions are welcome!
Feel free to submit issues, feature requests, or pull requests.

 License

MIT License – Free for personal and commercial use.
