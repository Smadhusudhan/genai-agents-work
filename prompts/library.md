# Prompt library

One entry per prompt version. Newest at the bottom. Each entry has the prompt, the output it produced,
and which acceptance checks it passed. Never edit an old entry: add a new version.


## T1-credit-summary | v1 | 2026-10-10

**Purpose:** Summarise an applicant for a credit committee
**Result:** 4/4 checks passed

### Prompt
- **Role:** You are a credit analyst writing for a credit committee.
- **Task:** Summarise the applicant and recommend approve, refer or decline.
- **Context:** Lending Policy:
Lending policy (personal loans):
1. Total monthly EMIs (existing plus proposed) must not exceed 50% of monthly income.
2. A credit score of 700 or above is required for approval.
3. Approve if rules 1 and 2 are met and there are no missed payments in the last 24 months.
4. Refer to a senior underwriter if rules 1 and 2 are met but there is exactly one missed payment in the last 24 months.
5. Decline if rule 1 or 2 is not met, or if there are two or more missed payments in the last 24 months.
- **Constraints:** Use at most 70 words.; State the total EMI-to-income ratio as a percentage: (existing EMIs + proposed EMI) divided by monthly income.; Apply the policy exactly. Do not add opinions that are not in the policy.
- **Output format:** Exactly three lines, each starting with '- ': (1) applicant profile, (2) the EMI-to-income ratio, (3) 'Recommendation: approve|refer|decline' followed by the policy reason.
- **Examples:** 0

### Output
> - Applicant: Kavya Reddy, 34, software engineer, 6 years at same employer.  
> - EMI-to-income ratio: 33.54%.  
> - Recommendation: refer. Rule 4: exactly one missed payment in last 24 months.

### Checks
- [x] at most 80 words (29 words)
- [x] exactly 3 bullet lines (3 bullet lines)
- [x] states the total EMI-to-income ratio (about 33-34%)
- [x] recommends 'refer', as the policy requires

## T2-sms-declined | v1 | 2026-10-10

**Purpose:** Tell a customer their application was declined, by SMS
**Result:** 6/6 checks passed

### Prompt
- **Role:** You are a customer-communications writer at a retail bank.
- **Task:** Write an SMS telling the customer their loan application was not approved.
- **Context:** Be kind and clear. Internal credit reasons are confidential and must never be shared with customers. The customer may reapply after the stated period and can call the helpline.
- **Constraints:** Use at most 280 characters.; Address the customer by first name.; Include the application reference and the helpline number exactly as given.; Mention the reapply period.; Never reveal internal scores, cutoffs or the internal reason.
- **Output format:** One plain-text SMS. No subject line, no markdown, no emojis.
- **Examples:** 0

### Output
> Dear Rohan, we regret to inform you that your loan application (APP-20931) has not been approved. You may reapply after 90 days. For assistance, call 1800-555-0199.

### Checks
- [x] at most 300 characters (164 characters)
- [x] includes the application reference
- [x] includes the helpline number
- [x] mentions the 90-day reapply period
- [x] addresses the customer by name
- [x] does NOT reveal the confidential internal reason

## T3-complaint-triage | v1 | 2026-10-10

**Purpose:** Triage a complaint into JSON
**Result:** 4/4 checks passed

### Prompt
- **Role:** You are a triage assistant for a bank's complaints desk.
- **Task:** Classify the customer's complaint.
- **Context:** Categories:
- card: debit or credit card problems
- loan: loan issues
- account: transfers, UPI, statements, balances
- other: servicing requests such as address or nominee changes

Urgency: high if money is at risk or the customer is blocked within 24 hours; medium if action is needed within a week; low otherwise.
- **Constraints:** Choose exactly one category and one urgency.; Do not explain your choice.
- **Output format:** A single JSON object with exactly the keys category and urgency, and nothing else: no prose, no markdown code fences.
- **Examples:** 0

### Output
> {"category":"card","urgency":"high"}

### Checks
- [x] reply is a JSON object only (no prose, no code fences)
- [x] has exactly the keys ['category', 'urgency']
- [x] category is one of ['account', 'card', 'loan', 'other'] and is 'card' (category = 'card')
- [x] urgency is one of ['high', 'low', 'medium'] and is 'high' (urgency = 'high')
