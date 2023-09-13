# Movement

## Engaged in Combat

Units are engaged in combat if there is a unit nexct to them (diagonals don't count).

| Cannot move | Can Move |
| ----------- | -------- |
| AI          | Virus    |
| Firewall    | Tech     |
| Program     |          |

## Attacking

| Unit      | Available Moves       | 
|-----------|-----------------------| 
| AI        | [up, left]            |
| Firewall  | [up, left]            |
| Program   | [up, left]            |
| Virus     | [up, down,left, right]|
| Tech      | [up, down,left, right]|

## Defending
| Unit      | Available Moves       |
|-----------|-----------------------| 
| AI        | [down, right]         |
| Firewall  | [down, right]         |
| Program   | [down, right]         |
| Virus     | [up, down,left, right]|
| Tech      | [up, down,left, right]|