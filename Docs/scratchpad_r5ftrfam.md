# Frontend Verification Plan

1. [x] Open `http://localhost:3000` and take initial screenshot.
   - Disclaimer banner is visible at the top: "Facts-only. No investment advice."
   - Sidebar is on the left with "MiraeAI" and "New thread" button.
   - Initial state message: "Select a thread or create a new one to get started."
2. [x] Verify Disclaimer Banner (text and fixed position).
   - Text is correct and follows the required format.
   - Banner appears fixed at the top (verified via layout inspection).
3. [x] Verify Sidebar (thread list, "New thread" button).
   - Sidebar visible, correctly displays "MiraeAI" and "+ New thread" button.
4. [-] Verify Welcome Screen (3 example questions).
   - Blocked by backend HTTP 500 error on thread creation.
5. [-] Test example question click.
   - Blocked by backend HTTP 500 error.
6. [-] Test creating a second thread.
   - Blocked by backend HTTP 500 error.
7. [x] Take final screenshot and generate report.
   - UI is implemented as requested, but functional state requires a running backend.