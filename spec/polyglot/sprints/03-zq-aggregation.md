# Sprint 03: ZQ Aggregation & Arrays

**Goal:** Add array operations, aggregation, and slurp mode to ZQ

**Prerequisite:** Sprint 02 complete

---

## Deliverables

1. Array iteration and operations
2. Slurp mode for aggregation
3. Group/sort/unique operations
4. Full feature parity with ZQ.md spec

---

## Phase 1: Array Iteration

### Basic Iteration
- [ ] `.[]` - iterate array elements
- [ ] `.items[]` - iterate nested array
- [ ] `.[] | select(...)` - filter array elements

### Array Access
- [ ] `first` - first element
- [ ] `last` - last element
- [ ] `nth(n)` - nth element
- [ ] `.[n:m]` - slice

### Quality Gate
- [ ] `echo '{"items":[1,2,3]}' | zq '.items[]'` → `1\n2\n3`
- [ ] Iteration works with pipes

---

## Phase 2: Array Functions

### Basic Functions
- [ ] `length` - array length
- [ ] `reverse` - reverse array
- [ ] `sort` - sort array
- [ ] `unique` - remove duplicates
- [ ] `flatten` - flatten nested arrays

### Search
- [ ] `contains(x)` - check if contains
- [ ] `index(x)` - find index of element
- [ ] `inside(arr)` - check if inside

### Construction
- [ ] `[.x, .y]` - array literal
- [ ] `[.items[] | .name]` - array comprehension

### Quality Gate
- [ ] `echo '[3,1,2]' | zq 'sort'` → `[1,2,3]`
- [ ] All array functions work

---

## Phase 3: Slurp Mode

### Implementation
- [ ] `-s` flag to read all input into array
- [ ] `inputs` function to slurp remaining
- [ ] Handle memory for large inputs

### Use Cases
- [ ] `zq -s 'length'` - count records
- [ ] `zq -s 'add'` - sum all values
- [ ] `zq -s 'group_by(.type)'` - grouping

### Quality Gate
- [ ] `echo -e '1\n2\n3' | zq -s 'add'` → `6`
- [ ] Slurp mode handles 100K+ records

---

## Phase 4: Aggregation Functions

### Basic Aggregation
- [ ] `add` - sum numbers or concat arrays
- [ ] `min` - minimum value
- [ ] `max` - maximum value
- [ ] `min_by(.field)` - min by field
- [ ] `max_by(.field)` - max by field

### Grouping
- [ ] `group_by(.field)` - group by field value
- [ ] `unique_by(.field)` - unique by field
- [ ] `sort_by(.field)` - sort by field

### Quality Gate
- [ ] Grouping produces correct nested structure
- [ ] Aggregation handles empty arrays

---

## Phase 5: Map Function

### Implementation
- [ ] `map(expr)` - transform each element
- [ ] `map(select(...))` - filter in map
- [ ] `map({...})` - transform to objects

### Advanced
- [ ] `map_values(expr)` - transform object values
- [ ] `to_entries` - object → array of {key, value}
- [ ] `from_entries` - array of {key, value} → object
- [ ] `with_entries(expr)` - transform entries

### Quality Gate
- [ ] `echo '[1,2,3]' | zq 'map(. * 2)'` → `[2,4,6]`
- [ ] Entry functions work correctly

---

## Phase 6: String Functions

### Basic
- [ ] `split(sep)` - string → array
- [ ] `join(sep)` - array → string
- [ ] `ascii_downcase` - lowercase
- [ ] `ascii_upcase` - uppercase

### Matching
- [ ] `startswith(s)` - prefix check
- [ ] `endswith(s)` - suffix check
- [ ] `contains(s)` - substring check
- [ ] `ltrimstr(s)` - trim prefix
- [ ] `rtrimstr(s)` - trim suffix

### Quality Gate
- [ ] `echo '"a,b,c"' | zq 'split(",")'` → `["a","b","c"]`
- [ ] All string functions work

---

## Phase 7: Final Testing

### Performance Tests
- [ ] Slurp 100K records < 500ms
- [ ] group_by 100K records < 1s
- [ ] map 100K records < 200ms

### Compatibility Tests
- [ ] All ZQ.md features implemented
- [ ] Compare outputs with jq for complex expressions

### Quality Gate
- [ ] Full ZQ spec implemented
- [ ] Performance targets met

---

## Success Criteria

| Feature | Target |
|---------|--------|
| `.[]` iteration | Working |
| `-s` slurp mode | Working |
| `group_by` | <1s for 100K |
| `map` | <200ms for 100K |
| `sort_by`, `unique_by` | Working |
| String functions | Working |
| ZQ.md spec coverage | 100% |

---

## Notes

**Deferred (not in ZQ scope):**
- Regex (test, match, sub, gsub)
- Recursion (recurse, walk)
- Variables (as $x)
- Modules (import, include)
