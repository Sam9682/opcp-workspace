# OPCP Frontend

React + TypeScript frontend application for the OPCP PSMC website.

## Tech Stack

- **React 18** - UI library
- **TypeScript** - Type safety
- **Vite** - Build tool and dev server
- **React Router** - Client-side routing
- **Axios** - HTTP client
- **Tailwind CSS** - Utility-first CSS framework

## Project Structure

```
src/
├── components/     # Reusable UI components
├── pages/          # Page components
├── services/       # API services
├── utils/          # Utility functions
├── App.tsx         # Main app component with routing
└── main.tsx        # Application entry point
```

## Getting Started

### Prerequisites

- Node.js 18+ and npm

### Installation

```bash
# Install dependencies
npm install
```

### Development

```bash
# Start development server
npm run dev
```

The application will be available at `http://ai-OPCP:5173`

### Build

```bash
# Build for production
npm run build
```

### Preview Production Build

```bash
# Preview production build locally
npm run preview
```

## Environment Variables

Create a `.env` file in the frontend directory:

```
VITE_API_BASE_URL=http://ai-OPCP:8000/api
```

## Features Implemented

- ✅ Project structure setup
- ✅ Tailwind CSS configuration
- ✅ React Router setup
- ✅ API service with Axios
- ✅ Authentication service
- ✅ Basic layout component
- ✅ Home page
- ✅ Login page
- ✅ Registration page
- ✅ Form validation utilities

## Next Steps

Future tasks will implement:
- Forum UI
- Payment integration UI
- Document management UI
- Event management UI
- Admin dashboard
- Notification preferences

## API Integration

The frontend connects to the FastAPI backend at `http://ai-OPCP:8000/api` by default. Make sure the backend is running before starting the frontend development server.

## Code Style

- Use functional components with hooks
- Use TypeScript for type safety
- Follow React best practices
- Use Tailwind CSS for styling
