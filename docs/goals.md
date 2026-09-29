Hackathon Guidelines: Banking Customer Service Agent
1. Objective & Scope

G1 – Goal. Build a customer service agent for banking. Based on the EDA so far, the best solution is to automate users' recurring questions.

G7 – Core focus. The central focus of this development is component (3): chatting with an agent.

2. Architecture

G4 – Repository structure. Keep the vertical-utilities design proposed in the repository. Each area is its own package:

security/
web/
ia/
3. Web Application

G2 – Interface. For simplicity, the user interface will be a web page.

G5 – Required components:

Landing page
User registration system (OAuth)
Option to chat with an agent

G3 – Security & testing. The website must have the highest possible, industry-standard level of security. Security tests and stress tests must be implemented.

G15 – Session timeout. The session closes automatically after 5 minutes of inactivity.

G21 – Event logging. Every event on the website must be logged, with a retention period of X days (to be defined).

4. User Data

G6 – Credentials. The hackathon provides a dataset of users. We must artificially generate a username and password for each of them.

5. Conversation Flow

G18 – Case selection. Before a conversation starts, the user is asked whether they want to open a new case or resume an existing one. If they choose "existing case," show their open cases plus the option to type the ID of the case they want to resume.

G8 – Input/output modes. The user can type their complaint or send a voice note. The agent always responds in text.

G9 – Typing indicator. Whenever the user sends a message, the UI waits 2 seconds and then shows a "typing" indicator, so the user doesn't lose patience while the agent reasons.

G10 – Phased rollout.

Phase 1: Perfect the text-only flow.
Phase 2: Using the perfected text flow, enable voice-to-text.

G14 – Languages. Must support queries in both Spanish and Portuguese.

G16 – Latency. Target response times under 1 second.

6. Agent Behavior & Intelligence

G11 – Reasoning. All reasoning is done by the text-to-text agent.

G12 – Difficulty-based routing. There must be a layer that measures the difficulty of the user's problem to decide which type of AI model handles it, in order to reduce costs.

G20 – Human escalation. The agent must recognize when to stop acting and hand the case over to a human. This logic lives in the AI-selection layer (G12).

G19 – Ambiguity handling. The agent must ask for clarification when a user's query is ambiguous and/or not understood.

G13 – Hard rules and closure protocol. Define hard rules for:

Repetitive messages
Off-topic messages
Aggressive behavior
Requests for confidential information belonging to anyone other than the user

When any of these is detected, the conversation is closed. The full protocol must be documented.

7. Case Persistence & Handoff

G17 – Case summary. The agent must leave a short but sufficient summary so another AI can resume the conversation.

Stored in a SQL table, keyed by an incident ID given to the user at the start of the incident.
To resume an incident, the user must provide the ID as an exact match.
The table must be queried at the incident_id + customer_id level, so users can never access other users' information.