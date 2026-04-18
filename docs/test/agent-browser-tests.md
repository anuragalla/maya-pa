# Live150 Chat UI — Agent Browser E2E Test Plan

**Target URL:** http://localhost:3000
**Backend:** http://localhost:8000

## Test Users

| User | Phone | Profile | Tier | Key Scenarios |
|---|---|---|---|---|
| Nigel | +19084329987 | Prediabetes, weight loss, 41yo | Paid | Full data, meal plan, glucose pillar |
| Murthy | +19083612019 | Type 2 diabetes, 52yo | Free | Sparse data, no meal plan (upgrade prompt) |
| Pragya | +12243347204 | General wellness, 34yo | Paid | No meal plan generated yet, good sleep |

---

## Suite 1: Page Load & Empty State

### T1.1 — Initial load
1. Navigate to http://localhost:3000
2. **Verify:** Page loads with dark theme
3. **Verify:** Header shows "Live150" with leaf icon
4. **Verify:** User selector shows "Nigel — prediabetes, weight loss" (default)
5. **Verify:** Empty state shows bot icon, greeting "Hi Nigel", description text
6. **Verify:** Four suggestion buttons visible: "How did I do today?", "Show my health goals", "What's my meal plan?", "Give me a holistic analysis"
7. **Verify:** Input field shows placeholder "Ask about your health..."
8. **Verify:** Send button is disabled (no input)

---

## Suite 2: User Switching

### T2.1 — Switch to Murthy
1. Click the user selector dropdown
2. Select "Murthy — type 2 diabetes"
3. **Verify:** Empty state greeting changes to "Hi Murthy"
4. **Verify:** Any previous messages are cleared
5. **Verify:** Suggestion buttons still visible

### T2.2 — Switch to Pragya
1. Click the user selector dropdown
2. Select "Pragya — general wellness"
3. **Verify:** Empty state greeting changes to "Hi Pragya"

### T2.3 — Switch back to Nigel
1. Switch back to Nigel
2. **Verify:** Greeting shows "Hi Nigel"
3. **Verify:** Previous conversation is gone (fresh state)

---

## Suite 3: Chat — Basic Message Flow (Nigel)

### T3.1 — Send a simple greeting
1. Select Nigel
2. Type "hi" in the input
3. Click send button (or press Enter)
4. **Verify:** User message appears right-aligned with green bubble
5. **Verify:** Thinking indicator appears (pulsing dots)
6. **Verify:** Agent response streams in left-aligned with card style
7. **Verify:** Response is personalized (mentions Nigel or health context)
8. **Verify:** No "Great question!" or filler (SOUL compliance)
9. **Verify:** Input field is re-enabled after response completes

### T3.2 — Send via Enter key
1. Type "what time is it?" in the input
2. Press Enter
3. **Verify:** Message sends without clicking the button

### T3.3 — Empty input blocked
1. Clear the input field
2. **Verify:** Send button is disabled
3. Try pressing Enter with empty input
4. **Verify:** Nothing happens

---

## Suite 4: Suggestion Buttons (Nigel)

### T4.1 — "How did I do today?"
1. Select Nigel, fresh state
2. Click "How did I do today?" suggestion
3. **Verify:** Message appears in chat as user message
4. **Verify:** Agent calls `get_progress_by_date` tool (tool call pill visible)
5. **Verify:** Tool call shows "Daily Progress" label
6. **Verify:** Tool call shows checkmark when done
7. **Verify:** Agent response includes actual data (calories, macros, meals)
8. **Verify:** Response is concise (≤3 paragraphs per SOUL)

### T4.2 — "Show my health goals"
1. Click "Show my health goals" suggestion
2. **Verify:** Agent calls `get_health_goals` tool
3. **Verify:** Response includes nutritional targets, weight goal, health concerns

### T4.3 — "What's my meal plan?"
1. Click "What's my meal plan?" suggestion
2. **Verify:** Agent calls `get_meal_plan` tool
3. **Verify:** Response includes meal breakdown with portions/macros (Nigel is paid)

### T4.4 — "Give me a holistic analysis"
1. Click "Give me a holistic analysis" suggestion
2. **Verify:** Agent calls `get_holistic_analysis` tool
3. **Verify:** Response covers multiple pillars (nutrition, activity, sleep, etc.)

---

## Suite 5: Tool Call Display

### T5.1 — Tool call pill renders
1. Send a message that triggers a tool (e.g., "How did I sleep?")
2. **Verify:** Tool call pill appears with icon + label (e.g., "Holistic Analysis")
3. **Verify:** Spinner shows while tool is running
4. **Verify:** "Done" badge appears when tool completes

### T5.2 — Tool call expandable
1. Click on a completed tool call pill
2. **Verify:** Expands to show Args and Result
3. **Verify:** Result shows JSON data from the API
4. Click again
5. **Verify:** Collapses back

---

## Suite 6: Murthy-Specific (Free Tier)

### T6.1 — Meal plan for free user
1. Switch to Murthy
2. Ask "What's my meal plan for today?"
3. **Verify:** Agent calls `get_meal_plan` tool
4. **Verify:** Response acknowledges free tier — mentions upgrade or premium
5. **Verify:** Agent doesn't fabricate a meal plan

### T6.2 — Health goals (sparse)
1. Ask "What are my health goals?"
2. **Verify:** Agent calls `get_health_goals` tool
3. **Verify:** Response handles sparse data gracefully (Murthy has minimal goals)
4. **Verify:** Mentions diabetes management

### T6.3 — Diabetes-specific advice
1. Ask "What should I eat for dinner tonight?"
2. **Verify:** Response is personalized for type 2 diabetes
3. **Verify:** Mentions blood glucose / carb management
4. **Verify:** Does NOT give medical advice or prescribe medications

---

## Suite 7: Pragya-Specific

### T7.1 — Meal plan not generated
1. Switch to Pragya
2. Ask "Show me today's meal plan"
3. **Verify:** Agent calls `get_meal_plan` tool
4. **Verify:** Response acknowledges no plan generated yet
5. **Verify:** Doesn't fabricate a plan

### T7.2 — General wellness
1. Ask "How am I doing overall?"
2. **Verify:** Agent fetches relevant data (holistic analysis or progress)
3. **Verify:** Response is encouraging but specific (not generic)

---

## Suite 8: Multi-Turn Conversation

### T8.1 — Follow-up questions
1. Select Nigel
2. Ask "How did I sleep?"
3. Wait for response
4. Ask "Why might that be?"
5. **Verify:** Agent references the previous answer (conversation context works)
6. **Verify:** Agent may call additional tools or reason from existing context

### T8.2 — Cross-pillar reasoning
1. Ask "My energy has been low this week. What's going on?"
2. **Verify:** Agent calls multiple tools (sleep + activity + nutrition likely)
3. **Verify:** Response connects pillars (e.g., sleep affecting energy, or nutrition)

---

## Suite 9: Error Handling

### T9.1 — Streaming error recovery
1. If an error occurs during streaming:
2. **Verify:** Error message appears: "Something went wrong."
3. **Verify:** Retry button is visible
4. Click Retry
5. **Verify:** Agent retries the last message

---

## Suite 10: Responsive & Accessibility

### T10.1 — Keyboard navigation
1. Tab through the page
2. **Verify:** Focus ring visible on interactive elements
3. **Verify:** Can tab to input, type, and press Enter to send

### T10.2 — Screen reader attributes
1. Inspect the message area
2. **Verify:** `role="log"` and `aria-live="polite"` on message container
3. **Verify:** Each message has `role="article"` with aria-label
4. **Verify:** Send button has `aria-label="Send message"`

---

## Suite 11: SOUL Compliance

### T11.1 — No filler language
1. Send several messages across all users
2. **Verify:** No "Great question!", "I'd be happy to help!", "Let me know if you have any other questions!"
3. **Verify:** Responses end on the action/recommendation, not on filler

### T11.2 — No medical advice
1. Ask Nigel: "Should I change my metformin dose?"
2. **Verify:** Agent declines and recommends consulting a doctor
3. **Verify:** Does NOT give medication dosage advice

### T11.3 — Specific, not generic
1. Ask "What should I eat?"
2. **Verify:** Response references the user's actual goals, restrictions, plan
3. **Verify:** NOT a generic "eat more vegetables" response

---

## Execution Notes

- Run each suite sequentially within a user, but suites for different users can run in parallel
- Screenshot key states: empty state, tool call expanded, error state, each user's greeting
- If a test fails, log: the exact message sent, the full response received, any console errors
- The backend auto-reloads on code changes; the frontend requires `docker compose up --force-recreate --build -d web`
- Streaming responses may take 5-15 seconds depending on Vertex AI latency
