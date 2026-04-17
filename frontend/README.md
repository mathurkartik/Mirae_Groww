# Mirae Asset Fund Explorer — Frontend

This is the Next.js frontend for the **Mirae Asset Fund Explorer & FAQ Assistant**. It features a modern 3-screen navigation system, interactive financial charts, and a floating AI chatbot.

## ✨ Key Features

- **Home Page**: Discover funds by category (Equity, Debt, Index, etc.).
- **Category Explorer**: Filter and sort funds in a specific group.
- **Fund Detail Dashboard**: 
  - **Interactive NAV Chart**: Growth of ₹10,000 visualizer using `recharts`.
  - **Portfolio Holdings**: Table view of top assets.
  - **Peer Comparison**: Compare with similar schemes.
- **Floating AI Assistant**: Persistent RAG-based chatbot widget for factual Q&A.
- **Premium Light Theme**: Clean, white/green aesthetic inspired by high-end fintech apps.

## 🚀 Getting Started

1. **Install dependencies**:
   ```bash
   npm install
   ```

2. **Configure environment**:
   Create a `.env.local` file with the backend API URL:
   ```env
   NEXT_PUBLIC_API_URL=http://localhost:8000
   ```

3. **Run the development server**:
   ```bash
   npm run dev
   ```

4. **Access the app**:
   Open [http://localhost:3000](http://localhost:3000) in your browser.

## 🏗️ Architecture

- **Framework**: Next.js 15 (App Router)
- **Styling**: Vanilla CSS (globals.css)
- **Charts**: Recharts
- **API Client**: Axios-based wrapper with Next.js rewrite proxy for secure backend communication.

---

> **Disclaimer:** Mutual fund investments are subject to market risks. This is an information-only tool and does not provide investment advice.
