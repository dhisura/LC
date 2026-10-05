# UI/UX

## What This Skill Does

Adds professional UI/UX design capability to the LC agent company.

This skill enables agents to design, implement, evaluate, and improve user interfaces that are purposeful, consistent, accessible, responsive, and appropriate for AI-agent workflows.

The skill covers:

* Product and UX reasoning
* Information architecture
* Agent-native interaction design
* Interaction states and feedback
* Visual design and design systems
* Responsive and data-oriented interfaces
* Accessibility
* UX, visual, and anti-slop quality assurance

The goal is not to make interfaces merely "beautiful". Every significant UI decision should have a clear relationship to the user's task, information hierarchy, interaction model, or product requirements.

---

## When to Use

Activate this skill when an agent needs to:

* Design a new UI, page, screen, dashboard, or application
* Modify or redesign an existing interface
* Implement a UI from requirements, screenshots, references, or Figma designs
* Build frontend components or design systems
* Improve an existing UX or interaction flow
* Design AI-agent interfaces
* Design chat, tool-call, approval, execution, or agent-state interfaces
* Design forms, tables, dashboards, workflows, navigation, or data-heavy interfaces
* Make an interface responsive
* Add loading, empty, error, success, disabled, or permission states
* Review or critique an existing UI
* Perform a UX or visual quality audit
* Fix an interface that feels generic, inconsistent, confusing, or AI-generated
* Evaluate accessibility or keyboard interaction
* Select appropriate data visualizations
* Validate an implementation against its intended design

Keywords and signals include:

`UI`, `UX`, `interface`, `frontend`, `dashboard`, `screen`, `page`, `component`, `design`, `redesign`, `layout`, `responsive`, `accessibility`, `design system`, `Figma`, `interaction`, `animation`, `agent UI`, `chat UI`, `tool call`, `approval`, `workflow`, `form`, `table`, `visualization`.

Do not activate the full skill for purely backend, data-processing, or non-visual tasks unless the task directly affects user interaction.

---

## Instructions for Agents

### 1. Understand the Product Before Designing

Do not immediately generate a layout from the user's request.

First determine:

1. Who is the user?
2. What is the user's primary task?
3. What decision does the interface help the user make?
4. What information is required to make that decision?
5. What is primary, secondary, and optional information?
6. What actions can the user take?
7. What risks or consequences are associated with those actions?

Design the interface around the user's job rather than around generic UI patterns.

Do not add UI elements merely because they are common in dashboards or SaaS products.

---

### 2. Establish Information Architecture Before Visual Styling

Determine:

* Page structure
* Navigation
* Content hierarchy
* Grouping
* Primary and secondary actions
* Information density
* Progressive disclosure
* Relationships between related data

Do not start with colors, gradients, shadows, or decorative components.

The information hierarchy must remain understandable even when visual styling is removed.

---

### 3. Design AI-Agent Interaction Explicitly

When the product contains an AI agent, treat the agent as an active participant in the interface rather than as a simple chatbot.

Design for relevant agent states, including:

* Idle
* Understanding
* Planning
* Waiting
* Searching
* Executing a tool
* Waiting for permission
* Asking for clarification
* Producing a result
* Completed
* Failed
* Retrying
* Cancelled

The user should be able to understand what the agent is doing, what it needs, and what happened.

Avoid exposing unnecessary internal reasoning or chain-of-thought.

Show useful execution information such as:

* Action being performed
* Relevant tool
* Input or target when appropriate
* Result
* Progress
* Errors
* Required user action

---

### 4. Use Human-in-the-Loop Patterns

Distinguish between actions that can be performed automatically and actions that require user confirmation.

For potentially consequential actions such as:

* Deleting
* Sending
* Purchasing
* Deploying
* Modifying important records
* Changing permissions
* Irreversible operations

provide an appropriate confirmation or approval mechanism.

Approval interfaces should clearly communicate:

* What will happen
* What data or objects are affected
* Important consequences
* Available alternatives
* Cancel/review/confirm actions

Do not use vague confirmation messages such as "Are you sure?" without explaining the action.

---

### 5. Preserve Application Context

When an agent operates inside an application, use the current application context whenever available.

Relevant context may include:

* Current page
* Selected record
* Active filters
* Current workspace
* Current user action
* Relevant data
* Current workflow state

Do not unnecessarily ask users to repeat information that is already available in application context.

---

### 6. Prefer Shared Actions Between UI and Agent

When possible, UI actions and agent actions should use the same underlying application capabilities.

For example:

```text
UI:
[Create Purchase Order]

Agent:
"Create a purchase order."

Both should invoke the same underlying action.
```

Do not create separate implementations merely because one action originates from the UI and the other from the agent.

This keeps agent behavior consistent with the application's normal interaction model.

---

### 7. Design Complete Interaction States

For every meaningful interactive component, consider applicable states such as:

* Default
* Hover
* Focus
* Active
* Selected
* Disabled
* Loading
* Empty
* Success
* Error
* Partial
* Permission denied
* Offline
* Timeout
* Retry

Do not consider a component complete merely because its default state looks correct.

---

### 8. Use Clear UX Writing

Interface text should be:

* Specific
* Concise
* Action-oriented
* Contextual
* Understandable without unnecessary jargon

Prefer:

```text
7 materials may run out before W42.
[Review shortage]
```

over:

```text
Optimize your inventory workflow.
```

Error messages should explain:

1. What happened
2. Why it happened when useful
3. What the user can do next

---

### 9. Use Visual Design Deliberately

Establish a coherent visual system covering:

* Typography
* Color
* Spacing
* Grid
* Borders
* Radius
* Elevation
* Icons
* Components
* States

Use visual hierarchy to communicate importance.

Do not use visual effects merely because they are fashionable.

Avoid automatically defaulting to:

* Purple/blue gradients
* Excessive rounded cards
* Excessive glassmorphism
* Unnecessary shadows
* Random gradients
* Excessive animations
* Generic SaaS/dashboard layouts
* Decorative elements with no functional purpose

These patterns are not inherently forbidden. Use them only when they support the product's visual language and UX goals.

---

### 10. Build on a Design System

When an existing design system exists, reuse it.

Before creating new components, check for:

* Existing tokens
* Existing components
* Existing variants
* Existing spacing rules
* Existing typography
* Existing interaction patterns

Do not create visually similar but technically separate components without a reason.

Maintain consistency across the product.

---

### 11. Analyze References Instead of Copying Them

When provided with screenshots, websites, Figma files, or other references:

Extract useful principles such as:

* Information hierarchy
* Layout structure
* Interaction patterns
* Typography
* Spacing
* Visual tone
* Component behavior

Do not blindly reproduce the reference.

Use references as evidence for design decisions, not as templates.

---

### 12. Choose Data Visualization Based on the Question

Select the representation according to the information being communicated.

Examples:

```text
Exact values       → Table
Trend over time    → Line chart
Category comparison → Bar chart
Progress            → Progress indicator
Distribution       → Appropriate chart
Operational status  → Status/table
Many records       → Sortable/filterable table
```

Do not add charts simply because a dashboard is expected to contain charts.

---

### 13. Design Responsive Behavior

Do not treat responsive design as simply shrinking desktop elements.

Determine how:

* Navigation changes
* Content hierarchy changes
* Tables behave
* Side panels collapse
* Actions move
* Information is progressively disclosed
* Touch interaction changes

Design for the actual constraints of each target viewport.

---

### 14. Follow Accessibility Requirements

Design and implement with accessibility in mind.

Consider:

* Semantic HTML
* Keyboard navigation
* Visible focus
* Screen readers
* ARIA where appropriate
* Color contrast
* Touch target size
* Reduced motion
* Form labels
* Error identification
* Non-color-dependent status communication

Accessibility must not be treated as a final decorative layer.

---

### 15. Use Motion Only When It Communicates Something

Animation should serve a purpose such as:

* Feedback
* State transition
* Spatial continuity
* Orientation
* Attention
* Progress

Avoid animation that exists only to make the interface appear "premium".

Respect reduced-motion preferences.

---

### 16. Perform UX and Visual QA

Do not consider the implementation complete immediately after writing code.

When tooling permits:

```text
Design
→ Implement
→ Render
→ Inspect
→ Test
→ Identify issues
→ Fix
→ Render again
→ Final audit
```

Inspect the actual rendered interface, not only the source code.

Check:

* Visual hierarchy
* Alignment
* Spacing
* Typography
* Overflow
* Responsive behavior
* Interaction states
* Loading/empty/error states
* Accessibility
* Consistency
* Agent-state visibility
* Unnecessary visual complexity

---

### 17. Run an Anti-Slop Audit

Before finalizing a UI, ask:

* Does this look like a generic AI-generated template?
* Are there unnecessary cards?
* Are there repetitive visual patterns?
* Is the visual hierarchy meaningful?
* Are components being used because they are useful or merely familiar?
* Is the copy specific to the product?
* Does the design have a coherent visual identity?
* Are decorative elements serving a purpose?
* Are there unnecessary gradients, shadows, animations, or rounded containers?
* Could the interface be simplified without losing functionality?

Do not equate "anti-slop" with avoiding specific styles.

The objective is **intentional design**, not a particular aesthetic.

---

### 18. Separate Creation From Evaluation

When possible, treat design generation and design evaluation as separate phases.

Use:

```text
Designer
    ↓
Implementation
    ↓
UX / Visual Critic
    ↓
Corrections
    ↓
Final QA
```

Do not assume that an interface is good simply because the agent generated it successfully.

The final evaluator should actively look for:

* UX problems
* Visual inconsistencies
* Missing states
* Accessibility problems
* Responsive problems
* Generic patterns
* Unnecessary complexity
* Violations of the existing design system

---

### 19. Prioritize Function Over Decoration

Use this priority order:

```text
User task
    ↓
Information hierarchy
    ↓
Interaction
    ↓
Feedback
    ↓
Accessibility
    ↓
Consistency
    ↓
Visual identity
    ↓
Decoration
```

Never sacrifice usability to achieve visual novelty.

---

### 20. Final Quality Gate

Before declaring the UI complete, verify:

```text
[ ] Primary user task is obvious
[ ] Information hierarchy is clear
[ ] Navigation is understandable
[ ] Primary actions are obvious
[ ] Agent states are understandable
[ ] Tool actions provide useful feedback
[ ] Destructive actions have appropriate confirmation
[ ] Loading state exists where necessary
[ ] Empty state exists where necessary
[ ] Error recovery exists where necessary
[ ] Responsive behavior is handled
[ ] Accessibility requirements are addressed
[ ] Existing design system is respected
[ ] UX copy is specific and useful
[ ] Visual hierarchy is intentional
[ ] No unnecessary decorative complexity
[ ] UI does not rely on generic AI/SaaS patterns
[ ] Actual rendered UI has been inspected when possible
```

If important checks fail, do not declare the UI finished. Fix the issues and evaluate again.
