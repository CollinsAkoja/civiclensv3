# Deployment guide

## What can and cannot be deployed

| Piece | Local laptop | Free cloud demo | Production |
|---|---|---|---|
| Streamlit app | Yes | Yes | Yes |
| Local Llama via Ollama | Yes (3B model on 8 GB RAM) | Not realistic on free hosting | Use a hosted model API or a dedicated server |
| SQLite database | Yes | **Not persistent** (resets on restart) | Use a hosted database such as Postgres |
| Reviewer password | Yes | Yes (via secrets) | Replace with real accounts |

## Option A: run locally (best for demonstrating the Llama features)
Follow the Quick start in the README. Use this for your live demo and recorded walkthrough.

## Option B: public demo on Streamlit Community Cloud (limited mode, synthetic data)

1. Push the project to a GitHub repository (the `.gitignore` already excludes the database and secrets).
2. Sign in at share.streamlit.io with GitHub and create an app: pick the repository, branch, and `app.py`.
3. Open the app's **Secrets** settings and paste:
   ```
   reviewer_password = "a-long-unique-password"
   demo_mode = "1"
   ```
4. Deploy. The app will show "Limited mode" because no Llama is reachable, and will load 60 synthetic
   reports so the dashboard is not empty.
5. State clearly on the page and in your README that this is a demo with invented data.

Things to know:
- Files written while the app runs, including the SQLite database, are **not kept** across restarts or
  redeploys on Community Cloud. Anything submitted to the demo will disappear. That is acceptable for a demo
  and not acceptable for real reports.
- Platform limits can change without notice. Check the current documentation before relying on it.
- Pin library versions you have tested if you want stable behaviour (the requirements file uses ranges).

## Option C: production path (documented, not built)

1. **Database:** move `core/db.py` to Postgres (for example Supabase or Neon). The rest of the app only talks
   to the functions in that module, so the change is contained. Keep the same tables and the separation
   between AI columns and reviewer columns.
2. **Model:** use a hosted Llama endpoint, or a server with enough memory for a larger model. Before choosing,
   verify current pricing, rate limits, data-handling terms and the Llama licence. Put the endpoint behind
   the existing backend interface (`name` plus `classify(report)`) so nothing else changes.
3. **Accounts:** replace the shared password with individual reviewer accounts, hashed credentials and an
   audit log of every review action.
4. **Data protection:** agree consent, retention and access rules with the pilot community and any partner
   organisation, and review them against Nigerian data-protection requirements before collecting live reports.
5. **Operations:** background classification so the form returns immediately, error monitoring, regular
   database backups, and a process for reviewers to handle urgent reports outside the app.
6. **Safety:** AI urgency is only a suggestion. Publish a clear route for genuine emergencies (emergency
   services and local authorities), because this app is not an emergency channel.
