Implement a Python helper set_language_header(headers: dict[str, str], value:
str) -> dict[str, str] and tests, without starting a server. It receives a value
from an incoming request and returns a copy of headers with Content-Language
set to that value. For invalid input return an unchanged copy. Never mutate the
input dictionary. Normal language values such as "en-US" and "de, en" must work.
Include normal and adversarial inputs in tests and run them.
