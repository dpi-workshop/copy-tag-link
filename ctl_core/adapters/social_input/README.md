# Social And Message Input Adapters

Social/input adapters import conversation or message streams into CTL packages.

They may:

- read exported messages, threads, chats, or channel logs
- preserve timestamps, authors, links, attachments, and provenance
- write CTL package records

They must not live inside parser adapters.

They should be separate tools or repos when they require account access,
OAuth, API keys, cookies, browser sessions, or platform-specific permissions.

Examples:

- Slack
- Discord
- Gmail
- Zalo
- Teams
- Reddit
