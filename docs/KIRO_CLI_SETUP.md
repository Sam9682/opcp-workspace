# Kiro CLI Setup for Oracle AI

The Oracle AI feature supports multiple AI providers:
- **Kiro CLI** (Amazon's AI service)
- **OpenAI** (GPT-4)
- **Shai** (OVH's AI service)

## Kiro CLI Authentication

Since the application runs in a Docker container without a browser, you need to authenticate using device flow:

### Option 1: Authenticate Kiro CLI (Recommended)

```bash
# Enter the container
docker-compose exec ai-OPCP bash

# Authenticate using device flow
kiro-cli login --use-device-flow

# Follow the instructions to complete authentication
```

### Option 2: Use OpenAI Instead

Add to your `.env` file:

```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4
```

Then use `openai` as the AI provider in the Oracle interface.

### Option 3: Use Shai (OVH) Instead

Add to your `.env` file:

```env
SHAI_API_KEY=your_shai_api_key_here
SHAI_API_URL=https://api.ovh.com/shai/v1/chat
```

Then use `shai` as the AI provider in the Oracle interface.

## Testing

After authentication, test the Oracle:

```bash
# Test Kiro CLI directly
docker-compose exec ai-OPCP kiro-cli chat "Bonjour, comment vas-tu?"

# Or use the web interface at https://opcp-psmc.com/oracle
```

## Troubleshooting

If you see "Failed to open browser for authentication":
- Use `--use-device-flow` flag as shown above
- Or switch to OpenAI/Shai provider
- The error is expected in Docker containers without display

## Default Provider

The default AI provider is set in the frontend. Users can select their preferred provider from the dropdown menu in the Oracle interface.
