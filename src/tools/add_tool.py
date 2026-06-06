from tools.registry import registry



def add(a:int , b: int) -> int:
    return a+b

ADD_SCHEMA = {
    "name": "add",
    "description": "计算两个整数的和，例如 a + b，a 和 b 都是整数",
    "parameters": {
        "type": "object",
        "properties": {
            "a": {
                "type": "integer",
                "description": "第一个整数",
            },
            "b": {
                "type": "integer",
                "description": "第二个整数",
            },
        },
        "required": ["a", "b"],
    },
}

registry.register(
    name="add",
    toolset="math",
    schema=ADD_SCHEMA,
    handler=lambda args, **kw: add(args["a"], args["b"]),
    emoji="🧮",
)

