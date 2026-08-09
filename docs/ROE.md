# KrakenBase – Rules of Engagement & Legal

**Version:** 0.1  
**Classification:** Unclassified – Training / Research / Authorized Defensive Use Only

## 1. Purpose Statement

KrakenBase is a passive spectrum monitoring and direction-finding system intended for:

- Authorized military / law-enforcement / government training
- Defensive spectrum awareness on controlled installations
- Research and development of SIGINT techniques under proper oversight
- Personal / hobby use only where local law permits passive reception

It is **not** an offensive electronic warfare system.

## 2. Hard Rules (Code Must Enforce)

1. **No transmission**  
   The software shall contain no code paths that enable RF transmission, jamming, spoofing, or active interrogation in v1. Any future transmit capability requires a separate, explicitly gated design review and is out of scope.

2. **Audit everything significant**  
   Every anomaly that triggers a DF dwell, every DOA result used for alerting, every mesh message sent, and every frequency hand-off must be written to the audit log with timestamp, event IDs, and reason.

3. **Confidence gating**  
   Alerts and hand-offs shall only occur when DOA confidence exceeds a configurable threshold (default high). Low-confidence results are logged but not acted upon.

4. **Return to scan**  
   After any dwell the system must return the Kraken array to its scanning / previous state. Permanent locking onto a frequency is forbidden without explicit operator override (not implemented in v1).

5. **Configuration over hard-coding**  
   Frequency lists, power thresholds, dwell times, and alert destinations are configuration. Changing operational behavior must not require code changes.

## 3. Operator Responsibilities

- Ensure the installation and use of the system complies with all applicable spectrum regulations and organizational policies.
- Maintain physical control of the antenna array and computing equipment.
- Review audit logs periodically.
- Do not point the system at frequencies or locations outside authorized collection authorities.
- Treat all collected location data as potentially sensitive.

## 4. Data Handling

- Raw IQ is not retained by default. Short recordings for analysis require explicit configuration and have retention limits.
- Event logs and baselines are operational data; protect them according to local policy.
- Mesh alerts contain only the minimum information necessary (frequency, bearing, confidence).

## 5. Prohibited Uses

- Targeting protected or unauthorized communications
- Any form of active electronic attack
- Covert surveillance of private individuals without legal authority
- Modification of the software to remove audit logging or confidence gates

## 6. Disclaimer

This software is provided for authorized use only. The authors and contributors accept no liability for misuse, regulatory violations, or operational consequences arising from deployment of this system. Users are solely responsible for compliance with all applicable laws and policies.

## 7. Version Control of ROE

Any change to these rules requires an update to this document and a corresponding version bump of the software. The running system should expose the active ROE version via the status API.
