# Flatten nested objects to dot notation
# No parameters required
# Usage: jn filter @builtin/flatten_nested
#
# Example:
#   Input:  {"user": {"name": "Alice", "age": 30}}
#   Output: {"user.name": "Alice", "user.age": 30}

def flatten_obj(prefix):
  . as $in
  | reduce keys[] as $key
    ({};
      if ($in[$key] | type) == "object" then
        . + ($in[$key] | flatten_obj(if prefix == "" then $key else prefix + "." + $key end))
      else
        . + {(if prefix == "" then $key else prefix + "." + $key end): $in[$key]}
      end
    );

flatten_obj("")
