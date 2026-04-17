The objective of this project is to build a **Mutual Fund Explorer & FAQ Assistant**. This platform transforms the traditional static fund discovery process into an interactive experience featuring a 3-screen navigation system (Home, Category, and Fund Detail) with high-performance historical NAV analytics, while retaining a facts-only RAG assistant as a persistent support widget. The system retrieves information exclusively from official public sources such as Mirae Asset AMC and MFAPI.in.
The system must strictly avoid providing investment advice, opinions, or recommendations. Every response must include a single, clear source link and adhere to defined constraints around clarity, accuracy, and compliance.

Objective
Design and implement a lightweight Retrieval-Augmented Generation (RAG)-based assistant that:
Answers factual queries about mutual fund schemes
Uses a curated corpus of official documents
Provides concise, source-backed responses

Target Users
Retail investors comparing mutual fund schemes
Customer support and content teams handling repetitive mutual fund queries

Scope of Work
1. Corpus Definition
Select one Asset Management Company (AMC)
Choose 3–5 mutual fund schemes, ensuring category diversity (e.g., large-cap, flexi-cap, ELSS)
Collect 15–25 official public URLs, including:
Scheme factsheets
KIM (Key Information Memorandum)
SID (Scheme Information Document)
AMC FAQ/help pages
AMFI/SEBI guidance pages
Statement and tax document download guides

2. FAQ Assistant Requirements
The assistant must:
Answer facts-only queries, such as:
Expense ratio of a scheme
Exit load details
Minimum SIP amount
ELSS lock-in period
Riskometer classification
Benchmark index
Process to download statements or capital gains reports
Ensure:
Each response is limited to a maximum of 3 sentences
Each response includes exactly one citation link
Each response includes a footer:
 “Last updated from sources: <date>”

3. Refusal Handling
The assistant must refuse non-factual or advisory queries, such as:
“Should I invest in this fund?”
“Which fund is better?”
Refusal responses should:
Be polite and clearly worded
Reinforce the facts-only limitation
Provide a relevant educational link (e.g., AMFI or SEBI resource)

3. User Interface (Explorer + Chat)
The solution features a modern 3-screen navigation system in a light-themed, premium UI:
- **Home**: Discovery landing page with category-based fund grouping.
- **Category Listing**: Filterable and sortable list of all schemes within a category.
- **Fund Detail**: deep-dive analytics dashboard with interactive historical NAV charts and portfolio holdings.
- **Floating AI Assistant**: A persistent chatbot widget accessible from any screen for factual Q&A.
- **Disclaimer Banner**: Always visible: “Facts-only. No investment advice.”

Constraints
Data and Sources
Use only official public sources (AMC, AMFI, SEBI)
Do not use third-party blogs or aggregator websites
Privacy and Security
Do not collect, store, or process:
PAN or Aadhaar numbers
Account numbers
OTPs
Email addresses or phone numbers
Content Restrictions
No investment advice or recommendations
No performance comparisons or return calculations
For performance-related queries, provide a link to the official factsheet only
Transparency
Responses must be short, factual, and verifiable
Every answer must include a source link and last updated date

Expected Deliverables
README Document
Setup instructions
Selected AMC and schemes
Architecture overview (RAG approach)
Known limitations
Disclaimer Snippet
“Facts-only. No investment advice.”
Multiple Chat Thread Support
A RAG-based chatbot capable of handling multiple independent conversations or threads simultaneously

Success Criteria
Accurate retrieval of factual mutual fund information
Strict adherence to facts-only responses
Consistent inclusion of valid source citations
Proper refusal of advisory queries
Clean, minimal, and user-friendly interface

Summary
The goal is to build a trustworthy, transparent, and compliant mutual fund FAQ assistant that prioritizes accuracy over intelligence. The system should ensure that users receive only verified, source-backed financial information, without any advisory bias or speculative content.
