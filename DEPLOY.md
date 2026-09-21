# Publish to Streamlit Community Cloud

1. Push this folder's contents to a GitHub repository (suggested name: `embark-fpa-demo`). Keep `.streamlit/config.toml`; never commit `.streamlit/secrets.toml` or `.env`.
2. Sign in at https://share.streamlit.io and create an app from that repository.
3. Select branch `main`, entry point `app.py`, and Python 3.12 in Advanced settings. Dependencies install from `requirements.txt`.
4. In Advanced settings → Secrets, add your own API key:

```toml
ANTHROPIC_API_KEY = "your-key-here"
```

5. Deploy and verify the dashboard and an AI scenario question. Without a key, the model still works and chat asks for a connection.

The server key enables AI requests for anyone who can access the deployed app, billed to that API account. Use private app access for a private demonstration. No API key is included in this package. Visitors never see API-key or model configuration fields; the floating assistant uses server secrets automatically.

The application uses illustrative data and independent branding inspired by Embark; it is not an official Embark application. Funnel diagnostic actuals are independently simulated, not a reconciliation to the forecast historical ledger.
