# Activity sync troubleshooting

Activity data is pulled from connected wearables via OAuth 2.0. Access tokens are refreshed automatically, but if the refresh token is revoked or expires (after 90 days of inactivity), the provider webhook returns HTTP 401 and sync stops.

Resolution: the user must re-authorise the integration under Settings > Connected apps, tap the watch or app you connected, then tap Reconnect. After re-authorisation, a backfill job imports the last 7 days of activity. Backfill typically completes within 15 minutes.
