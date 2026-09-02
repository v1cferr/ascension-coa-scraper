# Routes

One page. The viewer is a single surface whose state lives in the URL fragment, not
in a route tree.

| Route | File | Renders |
|---|---|---|
| `/` | `web/src/app/page.tsx` | The whole viewer (client component) |

## Addressing

State is carried in the hash so a finding can be sent rather than described:

| Address | Means |
|---|---|
| `#<realm>/<class>/<tree>` | a talent tree |
| `#<realm>/<class>/<tree>/<talentId>` | one talent chosen |
| `#<realm>/<class>/<tree>/<talentId>/<urlencoded model path>` | that talent's effect inspector open |
| `#spell/<id>` | a bare spell from the client's own table, belonging to no tree |
| `?play` | start the cast playing on arrival |

## API paths (proxied to the Python service by `web/src/middleware.ts`)

| Path | Returns |
|---|---|
| `/data/index.json` | realms, classes, trees, where assets live |
| `/data/search.json` | every talent in both realms, as compact arrays |
| `/data/<realm>/<class>/<tree>.json` | one tree's talents |
| `/data/client/effects/<realm>/<class>.json` | a class's resolved effects |
| `/_spells?q=` | search all 232,000 named spells |
| `/_spell/<id>` | one spell with its cast and who grants it |
| `/_model/<path>.m2` | what a model is made of |
| `/_texture/<path>.blp` | that texture decoded to PNG |
| `/_bundle/...` | assets as a zip |
