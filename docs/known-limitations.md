# Known Limitations

- External OpenAI, Pinecone, R2, Meta WhatsApp, ClamAV, Sentry, and production official-site access are not credential-tested.
- The local Compose file is not a production deployment manifest; it publishes PostgreSQL/Redis and uses development credentials.
- Python dependencies are not transitively hash-locked.
- OpenAI multilingual answer quality is not validated against a CIET-owned evaluation set.
- Accessibility automation now includes zero-violation axe runs, keyboard flow, focus return, responsive overflow, semantics, contrast, reduced motion, and accessible names, but not human screen-reader/assistive-technology acceptance.
- Conversation/query retention, consent, deletion, and object-storage disaster recovery are not automated.
- The CSP permits inline styles, and Nginx emits a generic server banner.
- Admissions, placement, content, and super-admin permissions are enforced with a live-tested least-privilege matrix; production user provisioning/offboarding remains an operational responsibility.
- Local chat-load evidence does not establish target-environment SLOs or external AI capacity.
