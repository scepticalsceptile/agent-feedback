# Agent-Feedback: A framework-agnostic way to tell your agent what it did wrong in 10 lines

**`agent_feedback` is a small Python library for one job:

1. call the model
2. (optional) pull out or edit the part you care about
3. check whether it is acceptable
4. try again with feedback if it is not**

(TODO: bold the above list properly)
Minimal code example:


```python

def web_search_reasonable_size(tool_call):

    raise RetryableFailure()

    

result = await arun(
	invoke=model.ainvoke,
	request=messages,
	extract=lambda response, request: response,
	validators=[require_tool_call],
	apply_feedback=append_feedback_message(role="system"),
	max_attempts=3,
)
```
(TODO: find a common eample for validation)

The mental model is:
(TODO: write the pipeline and then create a small graphic about how the pipeline runs from top to bottom)

(TODO: repace the emojis properly)


It is:
- (emoji: tick) Completely framework-agnostic - use any LLM API provider like Anthropic, OpenAI, or your own custom-built invokables
- (emoji: tick) Zero dependencies - no packages to manage, no transitive dependencies, lightning fast installs
- (emoji: tick) Plug-and-play middleware pattern built to be spammable  

While this is the focus, you can also use the middleware pattern for:


## Planned sections:


1. Where is this useful?
- Talk about: why not use instructor or pydantic_ai or something?
2. Built to be spammable - extra stuff you can do with the middleware pattern
- Augment tool calls with API keys or non-LLM handlable items
- Re-use your own previous pipeline - raise a RetryableFailure anywhere in the pipeline
- Validators are free evals, attach your own hooks
- Basically 0 cost to wrapping every invocation site in your application with this wrapper
3. Advanced tips and tricks(maybe link to another document)
- Type safety, how to type the functions and the request object
- How to use the functions as hooks
- How to use the Runner object
- Creating a custom decorator to wrap any function that throws, then catch that error to throw a RetryableFailure. Makes functions retryable 
