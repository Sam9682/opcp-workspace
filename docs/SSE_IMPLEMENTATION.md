# SSE (Server-Sent Events) Implementation for Oracle AI

## Overview

Implemented real-time streaming of AI responses using Server-Sent Events (SSE) for the Oracle AI feature.

## Backend Changes

### 1. Oracle Router (`app/oracle/router.py`)
- Added new endpoint: `POST /api/oracle/ask/stream`
- Streams AI responses in real-time using `StreamingResponse`
- Sends events with types: `start`, `token`, `done`, `error`
- Rate limited to 10 requests per minute (same as regular endpoint)

### 2. Oracle Service (`app/oracle/service.py`)
- Added `ask_oracle_stream()` method
- Streams response word-by-word for better UX
- Saves complete response to database after streaming
- Handles errors gracefully with error events

## Frontend Changes

### 1. Oracle Service (`frontend/src/services/oracleService.ts`)
- Added `askOracleStream()` method
- Uses `fetch` with `ReadableStream` for SSE
- Supports authentication via Bearer token
- Callbacks for: `onToken`, `onDone`, `onError`

### 2. Oracle Page (`frontend/src/pages/OraclePage.tsx`)
- Updated `handleSubmit` to use streaming
- Creates placeholder message that updates in real-time
- Shows tokens as they arrive from the AI
- Displays provider and processing time when complete

## How It Works

1. User submits a question
2. Frontend creates a placeholder message
3. Backend streams response word-by-word
4. Frontend updates the message content in real-time
5. When complete, backend saves to database and sends metadata
6. Frontend displays final provider info and processing time

## Benefits

- Better user experience with real-time feedback
- Users see responses as they're generated
- No waiting for complete response before display
- Maintains same database storage as before
- Graceful error handling

## Testing

1. Navigate to `/oracle` page
2. Select an AI provider (Kiro, Shai, or OpenAI)
3. Ask a question
4. Watch the response stream in real-time

## Notes

- SSE works with all AI providers (Kiro, Shai, OpenAI)
- Responses are still saved to database for history
- Rate limiting applies to both regular and streaming endpoints
- Authentication is supported via Bearer tokens
