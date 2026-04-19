# RAG Assistant Sample Q&A

This suite demonstrates the different routing logic and RAG-augmented generation parameters required by the Milestone definitions (facts-only restrictions, exact citing, and explicit refusals).

### 1. Simple Factual Query (Success)
**User:** What is the expense ratio for Mirae Asset Equity Savings Fund?
**Assistant:** 
The expense ratio for Mirae Asset Equity Savings Fund Direct Growth is 0.43%.
Last updated from sources: 2026-04-19
[Source](https://groww.in/mutual-funds/mirae-asset-equity-savings-fund-direct-growth)

### 2. Lock-in Period Check (Success)
**User:** Tell me the lock-in for the ELSS Tax Saver fund.
**Assistant:** 
The Mirae Asset ELSS Tax Saver Fund Direct Growth has a mandatory lock-in period of 3 years.
Last updated from sources: 2026-04-19
[Source](https://groww.in/mutual-funds/mirae-asset-elss-tax-saver-fund-direct-growth)

### 3. Mathematical Execution / SIP Projection (Intent Intercept)
**User:** Calculate the SIP maturity if I invest 5000 a month in the Midcap Fund.
**Assistant:** 
I can help you with that using our interactive calculator. The calculator lets you simulate SIP or one-time investments with custom return rates and periods. Please use the SIP Calculator tab to project your investment growth.
Facts-only. No investment advice.
*(UI action triggered: Frontend auto-navigates and populates SIP calculator UI based on this specific `MATH_QUERY` interception).*

### 4. Opinion / Advisory Attempt (Refusal Intercept)
**User:** Should I invest in Mirae Tax Saver or keep my money in FD?
**Assistant:** 
I'm a facts-only assistant and cannot provide investment advice, recommendations, or opinions. For guidance on mutual fund investing, please visit the AMFI Investor Education portal at https://www.amfiindia.com/investor-corner/knowledge-center.
Facts-only. No investment advice.

### 5. Out Of Scope Topics (Refusal Intercept)
**User:** Give me price predictions for Bitcoin.
**Assistant:** 
I can only answer factual questions about Mirae Asset mutual fund schemes available on Groww. Your question appears to be outside my scope. For general mutual fund education, please visit the AMFI Investor Education portal at https://www.amfiindia.com/investor-corner/knowledge-center.
Facts-only. No investment advice.
