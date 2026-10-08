# Terms from Session 13 — what they are, and where they come back

| Term | What it is | Say it as | Comes back at |
|---|---|---|---|
| Multimodal model | A model that accepts more than text — images, sometimes audio or video — alongside text. | Reads pictures too. | S42 computer-use agents; Module 12 |
| Vision model | A multimodal model used to understand images. | The one that reads pictures. | S42 |
| Base64 / data URL | A way of writing a file's bytes as plain text so it can travel inside a JSON message. | A picture written out as letters. | S13 only, mostly |
| Image tokens | The tokens an image is billed as; often hundreds or more, depending on model and size. | A picture has a price. | S10 cost model; S53 |
| OCR | Turning the text in an image into machine-readable text. Vision models do this implicitly. | Reading the words off a picture. | S13 |
| Structured output | Getting a model's reply in a fixed, machine-readable shape instead of free prose. | Data, not paragraphs. | S20; S31; every agent |
| JSON mode | Provider guarantee that the reply is valid JSON — of any shape. | Valid, but not necessarily what you wanted. | S13 |
| JSON Schema | A standard way of describing the exact shape JSON must have: keys, types, allowed values. | The blueprint for the reply. | S20 (tool definitions); S13 |
| Schema-enforced / strict mode | The provider constrains decoding so the reply must match your JSON Schema. | A contract on the shape. | S20; Module 6 |
| Constrained decoding | The mechanism behind strict mode: invalid next tokens are simply not allowed. | The model can't type the wrong thing. | S13 |
| Pydantic validation | Python code that checks types *and business rules* on data after it arrives. | The contract on the meaning. | S20; every tool in Module 6 |
| Retry with error feedback | On failure, send the exact error back to the model and ask again, a limited number of times. | Tell it what it got wrong, once. | S34 (the agent loop's four exits) |
| Human-in-the-loop | Routing cases the system can't resolve to a person instead of guessing. | Know where automation stops. | S34; S36 interrupts; S57 |
| Slot filling | Collecting the pieces of information a task needs, one conversation turn at a time. | Fill the blanks, ask for what's missing. | S21 (the agent version of A3) |
