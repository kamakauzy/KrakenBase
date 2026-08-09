# KrakenBase – Rules of Engagement

**Version:** 0.1  
These are hard operational constraints the agent and code must enforce.

## Hard Rules

1. **Passive only**  
   No transmit, jamming, spoofing, or active interrogation code paths in v1. Full stop.

2. **Audit significant actions**  
   Every DF dwell trigger, every DOA result used for an alert, every mesh message, and every frequency hand-off must be logged with timestamp, event IDs, and reason.

3. **Confidence gating**  
   Alerts and hand-offs only fire when DOA confidence exceeds the configured threshold. Low-confidence results are logged and discarded for action.

4. **Always return to scan**  
   After any dwell the array must be released back to scanning / previous state. No permanent lock without explicit operator override (not in v1).

5. **Config, not code**  
   Frequencies, thresholds, dwell times, bands, and alert destinations live in configuration. Changing behavior must not require editing source.

6. **No silent failures**  
   Kraken disconnect or data starvation must surface in health status. Do not pretend the sensor is fine when it is not.

7. **Rate-limit the mesh**  
   Do not spam Meshtastic with duplicate or low-value alerts. De-dupe by frequency + time window.

## Data Defaults

- Raw IQ is not retained by default.
- Short recordings (if ever enabled) need explicit config and retention limits.
- Mesh alerts stay minimal: frequency, bearing, confidence, short ID.

## Version

Bump this document and the software version together when the rules change. Expose the active ROE version via the status API.
