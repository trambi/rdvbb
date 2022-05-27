# rdvbb
Rendez-vous Bloodbowl website generator

Rendez-vous Bloodbowl is a french Bloodbowl that took place for the first time in 2003. 

Here is the basic static web site generator to generate website in `build` directory from REST API data :

```mermaid
flowchart LR
    api(REST API)--->generator[Generator]
    generator--->website[Content of build directory]
    generator-.->data[Cache json data]
```
