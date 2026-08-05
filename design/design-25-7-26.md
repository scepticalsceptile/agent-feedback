# Design 25-7-26

This document is a rough draft of the design for a clean-room sketch of agent-feedback. It is not a final design but is a starting point.

## Overview - user journey

Say the user is a developer using an llm-based application.

They want the LLM to generate something, within certain constraints.

However, LLMs are nondeterministic, and they may not always follow the constraints.

So one way we can mitigate this is: validate the output on whether the constraints are followed, and if not, provide feedback to the LLM to try again.

## Goal

Provide a framework-agnostic, intuitive 10-line API for developers to use to implement this feedback loop. Without describing it, here is the happy path API:

```python
from agent_feedback import arun, RetryableFailure

result = await arun(
	invoke=chat.completions.create, # or any other invokable
	request=messages,
    extract=lambda response, request: response.choices[0].tool_calls,
	validators=[tools_in_allowed_set],
	max_attempts=3,
)

allowed_set = {"search", "calculator"}
def tools_in_allowed_set(output):
    if not all(tool_call.name in allowed_set for tool_call in output):
        raise RetryableFailure(
            "Tool call not allowed",
            retry=True
        )
```

This will travel through a loop pipeline, following the arun() function top to bottom:

arun() -> invoke() -> extract() -> validators() -> go back to invoke() OR result

Before I go through these, its worth it to define some classes and types that will be used in the API:

## Key classes and types

### Quick note about sync vs async

We want to support both sync and async callables, but in this design we shall just speak about async callables. The complications regarding async callables shall be settled later. We need to discuss whether we want to support sync callables at all, or just require the user to wrap their sync callables in an async wrapper or provide a sync wrapper.

### Attempt object

This will carry all information throughout the pipeline. This is immediately created when arun() is called, and will be passed to each stage of the pipeline.

Attempt will have the following attributes:

```python

class Attempt(Generic[TRequest, TRawOutput, TOutput]):
    request: TRequest
    raw_output: TRawOutput | None
    output: TOutput | None
    retryable_failure: RetryableFailure | None
    attempt_number: int
    stage: AttemptStage
    metadata: dict[str, Any]

class AttemptStage(Enum):

    INVOKE = "invoke"
    EXTRACT = "extract"
    VALIDATE = "validate"
    SUCCESS = "success"

```

The AttemptStage details which stage of the pipeline the attempt is in.

We now have the AttemptHistory class, which will keep track of all attempts made in the pipeline.

This class should be an immutable list-like; you can do normal python list operations like indexing, slicing, and iteration, but you shouldn't modify it. We need to document this properly.

```python

class AttemptHistory(Sequence[Attempt[TRequest, TRawOutput, TOutput]]):
    max_attempts: int

    @property
    def last_attempt(self) -> Attempt[TRequest, TRawOutput, TOutput] | None:
        return self[-1] if self else None

```

... and maybe some other attributes and methods that I havent thought of yet like `last_success`, `_invoke`, `_ainvoke`, `_isasync: bool`, etc.

I sort of think this object should basically be the state storage of the entire pipeline rather than just a list of attempts. It can be the single source of truth for the entire pipeline, and should be passed to each stage of the pipeline.

### Run signature

```python

TRequest = Any | InvokeArgs
Invokable = Callable[..., Awaitable[TRawOutput] | TRawOutput]
Extractor = Callable[..., Awaitable[TOutput] | TOutput]
Validator = Callable[..., Awaitable[None] | None]
Retry = Callable[..., Awaitable[InvokeArgs] | InvokeArgs]

async def arun(
    *,
    invoke: Invokable,
    request: TRequest,
    extract: Extractor = identity,
    validators: list[Validator] = [],
    max_attempts: int = 3,
) -> HarnessResult[TRequest, TRawOutput, TOutput]:
```

## Step by step in the pipeline

Let's break down the steps:

### Step 1: Invoke

The invoke step is where we call the underlying function. This can be any callable, but it should be a callable that takes in the request (of any shape) and returns a response.

In the simplified path, if invoke() only has one argument and its positional (this is common for many libaries, where the request is a messages-containing object), TRequest is of type Any - you can pass in the message object of any shape directly, and it will go into the invoke() function as a single positional argument.

In the more general case, the request can be of any shape, we need to define a way to pass multiple arguments and keyword arguments to the underlying function. This is where the InvokeArgs object comes in.

#### The InvokeArgs object

```python
class InvokeArgs:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.args = args
        self.kwargs = kwargs
```

This is a very simple wrapper object. When the pipeline runs, we will simply do:

```python
raw_output = await invoke(*request.args, **request.kwargs)
```

if the request is of type InvokeArgs. Otherwise, we will do:

```python
raw_output = await invoke(request)
```

Now, at the end of the invoke stage, our Attempt object will have the following attributes:

```python
attempt = Attempt(
    request=request,
    raw_output=raw_output,
    output=None,
    retryable_failure=None,
    attempt_number=attempt_number,
    stage=AttemptStage.INVOKE,
    metadata={},
)
```

We can now move on to the next stage: extract.

### Stage 2: Extract

#### Why do we need this stage?

Often, the underlying function will return a response object that contains more information than we need. For example, the response object may contain metadata, status codes, etc. We only want to extract the relevant information - relevant in the sense that it affects our pipeline logic, such as being important in validation or feedback. This is where the extract() function comes in.

At its simplest, the extract() function can be a simple lambda function that takes in the response and returns the relevant information. For example:

```python
extract = lambda raw_response: raw_response.choices[0].message
```

That's it; no magic! Well, to be more precise, you can also access the request and entire history in case you want to do more complex extraction logic, like:

```python
def extract(response, _request, history):
    current_output = response.choices[0].message
    if len(history) > 1 and history[-1].metadata["llm_self_patch_attempt"]:
        attempt_json_patch(history[-2].output, current_output)
    return current_output # and then go into the validator to validate whether it was successful again. technically you can raise a RetryFailure here, but we want to keep some separation of concerns.
```

However, as you might notice, this stage is not strictly necessary. You can do the extraction logic in the validator function too, but we want to keep some separation of concerns. Another thing to keep note is that by default, the arun() function will return the EXTRACTED output, not the raw output, so that adds another utility to having this stage.

### Stage 3: Validate

This is the stage where we validate the output. The validators are a list of functions that take in the output and raise a RetryableFailure if the output is not valid.

The validation function has the following overloads, similar to extract() function, where you can access the entire history if you want to do more complex validation logic:

```python
def validator(output: TOutput) -> None:
    ...
def validator(output: TOutput, history: AttemptHistory) -> None:
    ...
```

Validators are called in order, and if any validator raises a RetryableFailure, the pipeline will go to retry stage. If all validators pass, the pipeline will exit with that output as the final output.

### Stage 4: Retry

Inside the validator (or anywhere inside the pipeline - more on that later), you will need to raise your own RetryableFailure:

```python
class RetryableFailure(Exception):
    def __init__(
        self,
        message: str,
        retry: Retry = lambda request: request,
    ) -> None:
        self.message = message
        self.retry = retry
```

Have a look at the retry parameter! This is a callable that takes in the request and returns a new request. This is for modifying the request for retrying the next invoke. For example, you can add a message to the messages list to tell the LLM what it did wrong and how to fix it. This is the crux - and its nested inside the error because retry is logically coupled to what is wrong with the output.

We allow the following overloads of retry function:

```python
def retry(request: TRequest) -> TRequest:
    ...
def retry(request: TRequest, error: RetryableFailure) -> TRequest:
    ...
def retry(request: TRequest, error: RetryableFailure, history: AttemptHistory) -> TRequest:
    ...
```

With the first overload:

```python
def validator(output: TOutput) -> None:
    if not is_valid(output):
        raise RetryableFailure(
            "Output is not valid",
            retry=lambda messages: messages + [Message("You messed up! Please try again!")],
        )
```

With the last overload:

```python
def x_condition_validator(output: TOutput) -> None:
    if not is_X_condition(output):
        raise RetryableFailure(
            "Output is not valid because it is not X condition",
            retry=lambda request, error, history: request + [Message(
                f"You messed up because {error.message}! You have already failed {history.num_attempts} times. Please try to do X properly!"
            )]
        )
```

Note that the request object can be either the single positional argument or the InvokeArgs object, depending on how the user passed in the request to arun(). You get back what you passed in, and you can modify it however you want. You can even return a completely new request object if you want to change the shape of the request.

And that's it! The pipeline will go back to the invoke stage with the new request, and the process will repeat until either the output is valid or the max_attempts is reached.

## Edge case 1: RetryableFailure raised anywhere other than the validator

The RetryableFailure can be raised anywhere in the pipeline, not just in the validator. For example, you can raise it in the invoke() function if you have some pre-validation logic that you want to enforce - things like structured output failures or network issues. You can also raise it in the extract() function if you want to enforce some extraction logic.

You can wrap any of these use cases in a simple decorator:

```python
P = ParamSpec("P")
R = TypeVar("R")

def retryable(
    retry: Retry = lambda request: request,
    catch_only: Type[BaseException] | tuple[Type[BaseException], ...] = Exception,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
                try:
                    return await func(*args, **kwargs)  # type: ignore[misc]
                except catch_only as e:
                    raise RetryableFailure(str(e), retry) from e
            return async_wrapper  # type: ignore[return-value]
        else:
            @functools.wraps(func)
            def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                try:
                    return func(*args, **kwargs)
                except catch_only as e:
                    raise RetryableFailure(str(e), retry) from e
            return sync_wrapper
    return decorator
```

Then you can slap on top:

```python

class Cat(BaseModel):
    name: str
    age: int
    color: str

@retryable(
    retry=lambda request, error: request + [Message(f"You messed up generating the schema because of {error.message}! Please try again!")],
    catch_only=StructuredOutputError,
)
def invoke(messages: list[Message], schema: Type[BaseModel]) -> Response:
    chat = ChatCompletion.create(
        model="gpt-4o",
        messages=messages,
        schema=schema,
        temperature=0.7,
        max_tokens=100,
    )
```

then just pass into arun:

```python
cat = await arun(
    invoke=invoke,
    request=InvokeArgs(messages, schema=Cat),
    max_attempts=3,
)
```

That's it! If your ChatCompletion returns a StructuredOutputError, it will be caught and wrapped into a RetryableFailure, and the pipeline will retry with the new request.

We can probably make this more specific to other things like pydantic validators etc, but for now we can use this generic one.

## Things I still need to write about:

- Type generics for request, response and output. can we more strongly type this or should these remain as any?
- Lifecycle hooks between the stages like on_invoke, on_extract, on_validate, on_feedback
- what to return at the end? need to specify that arun can have a param for the user to choose - default is the final success output, but can return raw_output, or the entire AttemptHistory, or the final Attempt object. Also let them choose if raise an exception if max_attempts is reached or just return the final Attempt object with the last RetryableFailure.

## Marketing stuff

- Extremely spammable, put it every invoke site, free callbacks, observability, and retries because why not.
- Compared to Instructor by 567 labs: ours is framework agnostic and our validation is more flexible. Instructor is a framework, and it ONLY validates and guarantees Structured Output. We literally validate anything with feedback.
- Compared to trustcall: You can emulate the JSON patching behaviour using the extract() function and history, but not recommended. You can use BOTH why not?
- Key point here: those are higher level frameworks that are opinionated; I'm trying to make a lower level framework that is more flexible and can be used to build higher level frameworks!
