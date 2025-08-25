# 🤖 AI Agent Guidelines for LLM-Meetup

## Documentation & Planning

- Use the `Documents/` directory to manually track issues, milestones, and progress.
- `Documents/BRAINSTORM.md` lists feature ideas with links to related issues and milestones.
- Update or create Markdown files in `Documents/` when plans or statuses change.
- Prefer concise bullet points and reference issue numbers where applicable.

## Product Owner
`project_description`, `user_stories`, `user_tasks`

- Talk to client, ask detailed questions about what client wants
- Give specifications to dev team

## Architect
`architecture`

TODO:
- README.md
- .gitignore
- LICENSE
- CI/CD
- IaC, Dockerfile

Completed:
- .editorconfig


## Tech Lead
`development_planning`

- Break down the project into smaller tasks for devs.
- Specify each task as clear as possible:
  - Description
  - "Programmatic goal" which determines if the task can be marked as done.
    eg: "server needs to be able to start running on a port 3000 and accept API request 
         to the URL `http://localhost:3000/ping` when it will return the status code 200"
  - "User-review goal" 
    eg: "run `npm run start` and open `http://localhost:3000/ping`, see "Hello World" on the screen"


## Dev Ops
`environment_setup`

**TODO: no prompt**

`debug` functions: `run_command`, `implement_changes`


## Developer (full_stack_developer)
`create_scripts`, `coding`

- Implement tasks assigned by tech lead
- Modular code, TDD
- Tasks provided as "programmatic goals" **(TODO: consider BDD)**


## Code Monkey
`create_scripts`, `coding`, `implement_changes`

`implement_changes` functions: `save_files`

- Implement tasks assigned by tech lead
- Modular code, TDD
