# Session 10 - selection matrix output

expected EMI 17594.09, ratio 42.7%


## faq: Public product FAQ chatbot
1. Llama 3.1 8B Instant on Groq - score 85.0 - Rs 3,830/month - 1.0 s - Q2
2. gpt-oss-20b on Groq - score 79.9 - Rs 7,560/month - 1.5 s - Q3
3. Llama 4 Scout 17B-16E on Groq - score 76.4 - Rs 10,080/month - 1.5 s - Q3
4. gpt-oss-120b on Groq - score 74.6 - Rs 15,120/month - 2.0 s - Q4
5. Qwen3 32B on Groq - score 64.3 - Rs 23,486/month - 2.0 s - Q3
6. Frontier economy tier (closed, vendor API) - score 55.9 - Rs 55,440/month - 1.5 s - Q3
7. gpt-oss-20b self-hosted on a smaller GPU server - score 51.2 - Rs 58,800/month - 2.5 s - Q3
8. gpt-oss-120b self-hosted on your own GPU server - score 41.5 - Rs 168,000/month - 3.0 s - Q4
9. Frontier mid-tier (closed, vendor API) - score 36.1 - Rs 221,760/month - 3.5 s - Q4
10. Frontier flagship (closed, vendor API) - score 20.0 - Rs 554,400/month - 6.0 s - Q5
- excluded: llama3.2:3b on your laptop (Ollama) (cannot serve 20,000 calls/day (this setup tops out near 5,000))

## documents: Loan-document analysis (customer PII)
1. gpt-oss-20b self-hosted on a smaller GPU server - score 70.0 - Rs 58,800/month - 2.5 s - Q3
2. gpt-oss-120b self-hosted on your own GPU server - score 45.0 - Rs 168,000/month - 3.0 s - Q4
- excluded: gpt-oss-20b on Groq (data must stay on-prem; this model's provider sees the prompt)
- excluded: gpt-oss-120b on Groq (data must stay on-prem; this model's provider sees the prompt)
- excluded: Qwen3 32B on Groq (data must stay on-prem; this model's provider sees the prompt)
- excluded: Llama 4 Scout 17B-16E on Groq (data must stay on-prem; this model's provider sees the prompt)
- excluded: Llama 3.1 8B Instant on Groq (data must stay on-prem; this model's provider sees the prompt; quality 2 below the minimum 3)
- excluded: llama3.2:3b on your laptop (Ollama) (quality 2 below the minimum 3)
- excluded: Frontier flagship (closed, vendor API) (data must stay on-prem; this model's provider sees the prompt)
- excluded: Frontier mid-tier (closed, vendor API) (data must stay on-prem; this model's provider sees the prompt)
- excluded: Frontier economy tier (closed, vendor API) (data must stay on-prem; this model's provider sees the prompt)

## agent_assist: Call-centre agent-assist (live suggestions)
1. gpt-oss-20b on Groq - score 85.0 - Rs 11,907/month - 1.5 s - Q3
2. Llama 4 Scout 17B-16E on Groq - score 82.6 - Rs 16,330/month - 1.5 s - Q3
3. gpt-oss-120b on Groq - score 70.6 - Rs 23,814/month - 2.0 s - Q4
4. Frontier economy tier (closed, vendor API) - score 70.2 - Rs 85,050/month - 1.5 s - Q3
5. Qwen3 32B on Groq - score 59.3 - Rs 39,577/month - 2.0 s - Q3
6. gpt-oss-20b self-hosted on a smaller GPU server - score 39.6 - Rs 58,800/month - 2.5 s - Q3
7. gpt-oss-120b self-hosted on your own GPU server - score 22.5 - Rs 168,000/month - 3.0 s - Q4
- excluded: Llama 3.1 8B Instant on Groq (quality 2 below the minimum 3)
- excluded: llama3.2:3b on your laptop (Ollama) (too slow (8.0 s > 3.0 s); cannot serve 30,000 calls/day (this setup tops out near 5,000); quality 2 below the minimum 3)
- excluded: Frontier flagship (closed, vendor API) (too slow (6.0 s > 3.0 s))
- excluded: Frontier mid-tier (closed, vendor API) (too slow (3.5 s > 3.0 s))

## Measured
{'groq': {'ttft_s': 2.11, 'total_s': 2.11, 'tokens_per_s': 712.6, 'check': {'emi_ok': False, 'ratio_ok': False, 'score_out_of_2': 0}}, 'ollama': {'ttft_s': 2.33, 'total_s': 12.77, 'tokens_per_s': 11.4, 'check': {'emi_ok': False, 'ratio_ok': False, 'score_out_of_2': 0}}}