# Pre-read for Session 13 — ten minutes

**An image is just more content in the message.** A normal message has `content` as a string. For vision, `content` becomes a *list*: one text part, one image part. The image part carries the picture as a long string of letters and digits (base64) or a link. The model receives it and "reads" it, and you pay for it in tokens — often hundreds or more per image, depending on the model and the image size, which changes the cost arithmetic from Session 10.

**A vision model and a text model can be different models.** Today's pipeline uses one to read the picture (turning it into text) and another to turn that text into a clean record. Splitting the job lets you use the cheapest model that is good enough at each step.

**Asking for JSON has three levels.**
1. *Ask nicely* ("reply with JSON only"): a request. Models usually comply and sometimes wrap the JSON in a sentence or a markdown fence.
2. *JSON mode*: the provider guarantees the reply is valid JSON — of **any** shape. The keys might be wrong.
3. *Schema-enforced*: you hand over a JSON Schema and the provider constrains the model to it. The shape is guaranteed (on models that support strict mode — `gpt-oss-20b` does).

**Shape is not truth.** Even level 3 only guarantees that `date_of_birth` is a string. It cannot know the date is in the future, or that an ID number has the wrong pattern, or that the vision step misread a letter as a digit. Those are *business rules*, and they live in your code — here, in a Pydantic model. Types and rules together are the contract downstream systems rely on.

**When validation fails: retry once, then ask a human.** Feeding the exact error back to the model fixes formatting slips. It cannot fix a fact the input never contained. Deciding where automation stops and a person starts is a design decision, not a bug.

**Three questions to arrive with**
- Why might a bank use a cheap model to read an image and a different model to structure the result?
- If a provider guarantees "valid JSON", what could still be wrong with the reply?
- A document scan is blurry and the ID number is ambiguous. What should the system do?
