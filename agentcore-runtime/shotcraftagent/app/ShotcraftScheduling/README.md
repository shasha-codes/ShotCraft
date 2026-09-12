# ShotCraft AgentCore runtime

This runtime hosts ShotCraft's Strands reasoning workflows behind one bounded
AgentCore entrypoint. FastAPI supplies validated application facts and remains
responsible for persistence, authorization, human approvals, and mutations.

Supported operations:

- `inquiry_intake`: tool-assisted inquiry and follow-up assessment
- `creative_direction`: tool-assisted brief and moodboard planning
- `cancellation_review`: evidence-backed recommendation for the photographer
- `structured_completion`: production packs, change assessments, client drafts,
  and shoot-idea recommendations
- default scheduling payload: ranks server-validated schedule candidates

The runtime reads the Mantle bearer key from the Secrets Manager secret whose
ARN is provided through `SHOTCRAFT_BEDROCK_SECRET_ARN`. Never commit that key.

Deploy from the AgentCore project root:

```bash
agentcore validate
agentcore deploy --target shotcraft-account-a --yes
agentcore status
```
