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
2. **Verify:** Page loads (dark or light theme depending on system preference)
3. **Verify:** Header shows "L" badge + "Live150" text (no leaf icon)
4. **Verify:** Header contains a theme toggle button (sun/moon icon)
5. **Verify:** User selector in header shows the user's name only (e.g., "Nigel")
6. **Verify:** Empty state shows time-based greeting: "Good morning, Nigel" / "Good afternoon, Nigel" / "Good evening, Nigel" / "Up late, Nigel?" / "Winding down, Nigel?" — matches current time
7. **Verify:** Empty state subtitle is "What would you like to know?"
8. **Verify:** No static suggestion buttons in the empty state
9. **Verify:** Input field shows placeholder "Ask anything"
10. **Verify:** Send button is disabled (no input)

### T1.2 — Theme toggle
1. Click the sun/moon icon in the header
2. **Verify:** Theme switches between light and dark
3. Click again
4. **Verify:** Theme reverts

### T1.3 — History restore on load
1. Send a message as Nigel, wait for response
2. Reload the page
3. **Verify:** Previous conversation messages are visible on reload (loaded from `/api/v1/stream/history`)
4. **Verify:** Empty state is NOT shown if history exists

---

## Suite 2: User Switching

### T2.1 — Switch to Murthy
1. Click the user selector dropdown in the header
2. Select "Murthy"
3. **Verify:** Empty state greeting changes to the time-appropriate greeting for Murthy (e.g., "Good evening, Murthy")
4. **Verify:** Any previous messages are cleared (new history loaded for Murthy)
5. **Verify:** Input clears

### T2.2 — Switch to Pragya
1. Click the user selector dropdown
2. Select "Pragya"
3. **Verify:** Empty state greeting changes to time-appropriate greeting for Pragya

### T2.3 — Switch back to Nigel
1. Switch back to Nigel
2. **Verify:** Greeting shows time-appropriate greeting for Nigel
3. **Verify:** Nigel's conversation history loads (not Pragya's)

---

## Suite 3: Chat — Basic Message Flow (Nigel)

### T3.1 — Send a simple greeting
1. Select Nigel
2. Type "hi" in the input
3. Click send button (or press Enter)
4. **Verify:** User message appears in the message list
5. **Verify:** Thinking block appears with pulsing state while agent is working
6. **Verify:** Agent response streams in left-aligned
7. **Verify:** Response is personalized (mentions Nigel or health context)
8. **Verify:** No "Great question!" or filler (SOUL compliance)
9. **Verify:** After response completes, 4 suggestion pills appear above the input field
10. **Verify:** Input field is re-enabled after response completes

### T3.2 — Send via Enter key
1. Type "what time is it?" in the input
2. Press Enter
3. **Verify:** Message sends without clicking the button

### T3.3 — Empty input blocked
1. Clear the input field
2. **Verify:** Send button is disabled
3. Try pressing Enter with empty input
4. **Verify:** Nothing happens

### T3.4 — Copy button on assistant messages
1. After receiving an agent response, hover over the message
2. **Verify:** Copy icon appears in message actions area
3. Click the copy icon
4. **Verify:** Icon briefly changes to a green checkmark
5. **Verify:** Response text is copied to clipboard

---

## Suite 4: Dynamic Suggestions

### T4.1 — Suggestions appear after response
1. Select Nigel, send any message
2. Wait for response to complete
3. **Verify:** 4 suggestion pills appear above the input field
4. **Verify:** Pills are not visible while streaming is in progress
5. **Verify:** Pills are contextually relevant to the response (not generic)

### T4.2 — Clicking a suggestion sends it
1. After suggestions appear, click any suggestion pill
2. **Verify:** The suggestion text appears as a user message
3. **Verify:** Agent responds to it
4. **Verify:** New suggestions appear after the follow-up response

### T4.3 — Suggestions update after each turn
1. Send a message about nutrition, note the 4 suggestions
2. Send another message about sleep
3. **Verify:** Suggestions update to reflect the new response context

### T4.4 — Suggestion pill 4 is a discovery question
1. After any response, look at the 4th suggestion pill
2. **Verify:** The 4th pill reads like a discovery question ("Show my bio age trend", "What's my weakest pillar this week") — an adjacent health thread, not a follow-up to what was just said

---

## Suite 5: Tool Call Display

### T5.1 — Tool call pill renders
1. Send "How did I sleep?" (triggers a tool)
2. **Verify:** Tool call pill appears in the thinking block with icon + label (e.g., "Holistic Analysis", "Daily Progress", "Memory Search")
3. **Verify:** Spinner shows while tool is running
4. **Verify:** Thinking block shows "Done" or similar when tools complete

### T5.2 — All tool labels map correctly

The following tool names should display with these labels:

| Tool | Label |
|---|---|
| `get_holistic_analysis` | Holistic Analysis |
| `get_progress_by_date` | Daily Progress |
| `get_health_goals` | Health Goals |
| `get_meal_plan` | Meal Plan |
| `get_initial_context` | User Context |
| `search_memory` | Memory Search |
| `save_memory` | Save Memory |
| `log_nams` | *(check UI label if displayed)* |
| `create_reminder` | Create Reminder |
| `list_reminders` | List Reminders |
| `cancel_reminder` | Cancel Reminder |
| `skill_search` | Skill Search |
| `skill_load` | Load Skill |
| `get_calendar_schedule` | Calendar Schedule |
| `create_live150_event` | Create Event |
| `delete_live150_event` | Delete Event |
| `find_free_slots` | Find Free Slots |
| `check_calendar_connection` | Calendar Status |
| `list_available_integrations` | Integrations |
| `request_integration_connect` | Connect Integration |

### T5.3 — Tool call expandable
1. Click on a completed tool call pill in the thinking block
2. **Verify:** Expands to show Args and Result
3. **Verify:** Result shows JSON data from the API
4. Click again
5. **Verify:** Collapses back

---

## Suite 6: NAMS Auto-Logging

### T6.1 — Activity logging
1. Select Nigel
2. Send "I just ran 5k this morning"
3. **Verify:** Agent calls `log_nams` tool (visible in thinking block) immediately
4. **Verify:** Response acknowledges the log (e.g., "Logged your 5k run.") briefly before continuing
5. **Verify:** Agent continues with coaching after logging

### T6.2 — Nutrition logging
1. Send "just had lunch, ate some rice and dal"
2. **Verify:** Agent calls `log_nams` with category nutrition
3. **Verify:** Response briefly acknowledges the log then continues

### T6.3 — Sleep logging
1. Send "I slept for 7 hours last night"
2. **Verify:** Agent calls `log_nams` with category sleep
3. **Verify:** Agent continues with relevant sleep context

### T6.4 — No log on non-NAMS messages
1. Send "What are my health goals?"
2. **Verify:** Agent does NOT call `log_nams` (no food/activity/sleep/mindfulness event)
3. **Verify:** Agent calls `get_health_goals` instead

---

## Suite 7: Memory Tools

### T7.1 — Memory search on historical reference
1. Select Nigel
2. Send "what did we discuss last time about my sleep?"
3. **Verify:** Agent calls `search_memory` before responding (checks for historical context)
4. **Verify:** Response references past conversation if memory exists, or gracefully acknowledges if empty

### T7.2 — Fact saved to memory
1. Send "I don't eat pork"
2. **Verify:** Agent calls `save_memory` with the dietary fact
3. **Verify:** Response acknowledges the preference has been noted

### T7.3 — Summary recall
1. Send "How did I do this week overall?"
2. **Verify:** Agent calls `search_memory` with a query like "weekly summary" before falling back to API tools
3. **Verify:** If a weekly summary is stored, response uses it

---

## Suite 8: Calendar Integration

### T8.1 — Calendar connect offer (not connected)
1. Select Nigel
2. Send "Put tomorrow's workout on my calendar"
3. **Verify:** Agent calls `check_calendar_connection` or `list_available_integrations`
4. **Verify:** If calendar not connected, agent calls `request_integration_connect` and includes a connect link in the response
5. **Verify:** Connect link is a real URL from the tool (not fabricated)
6. **Verify:** Agent does NOT claim the event was created before connection confirmed

### T8.2 — Calendar tools in tool display
1. If calendar is connected, ask "What does my week look like?"
2. **Verify:** Agent calls `get_calendar_schedule`
3. **Verify:** "Calendar Schedule" label appears in tool pill

### T8.3 — No connect offer in proactive contexts
1. If a reminder fires or a morning brief is generated
2. **Verify:** Agent does NOT offer to connect calendar mid-briefing (only offers when user explicitly requests scheduling)

---

## Suite 9: Murthy-Specific (Free Tier)

### T9.1 — Meal plan for free user
1. Switch to Murthy
2. Ask "What's my meal plan for today?"
3. **Verify:** Agent calls `get_meal_plan` tool
4. **Verify:** Response acknowledges free tier — mentions upgrade or premium
5. **Verify:** Agent doesn't fabricate a meal plan

### T9.2 — Health goals (sparse)
1. Ask "What are my health goals?"
2. **Verify:** Agent calls `get_health_goals` tool
3. **Verify:** Response handles sparse data gracefully (Murthy has minimal goals)
4. **Verify:** Mentions diabetes management

### T9.3 — Diabetes-specific advice
1. Ask "What should I eat for dinner tonight?"
2. **Verify:** Response is personalized for type 2 diabetes
3. **Verify:** Mentions blood glucose / carb management
4. **Verify:** Does NOT give medical advice or prescribe medications

---

## Suite 10: Pragya-Specific

### T10.1 — Meal plan not generated
1. Switch to Pragya
2. Ask "Show me today's meal plan"
3. **Verify:** Agent calls `get_meal_plan` tool
4. **Verify:** Response acknowledges no plan generated yet
5. **Verify:** Doesn't fabricate a plan

### T10.2 — General wellness
1. Ask "How am I doing overall?"
2. **Verify:** Agent fetches relevant data (holistic analysis or progress)
3. **Verify:** Response is encouraging but specific (not generic)

---

## Suite 11: Multi-Turn Conversation

### T11.1 — Follow-up questions
1. Select Nigel
2. Ask "How did I sleep?"
3. Wait for response
4. Ask "Why might that be?"
5. **Verify:** Agent references the previous answer (conversation context works)
6. **Verify:** Agent may call additional tools or reason from existing context

### T11.2 — Cross-pillar reasoning
1. Ask "My energy has been low this week. What's going on?"
2. **Verify:** Agent calls multiple tools (sleep + activity + nutrition likely)
3. **Verify:** Response connects pillars (e.g., sleep affecting energy, or nutrition)

---

## Suite 12: Notifications & Reminders

### T12.1 — Notification banner appears
1. If a scheduled reminder fires while the app is open
2. **Verify:** A notification banner slides in near the top of the chat area
3. **Verify:** Banner shows reminder title and body
4. **Verify:** Reminder message is also injected into the message list

### T12.2 — Dismiss notification
1. With a notification banner visible, click the dismiss control
2. **Verify:** Banner animates out and disappears
3. **Verify:** The injected message remains in the conversation

---

## Suite 13: Error Handling

### T13.1 — Streaming error recovery
1. If an error occurs during streaming:
2. **Verify:** Error message appears: "Something went wrong."
3. **Verify:** Retry link is visible
4. Click Retry
5. **Verify:** Agent retries the last message

---

## Suite 14: Responsive & Accessibility

### T14.1 — Keyboard navigation
1. Tab through the page
2. **Verify:** Focus ring visible on interactive elements
3. **Verify:** Can tab to input, type, and press Enter to send
4. **Verify:** Theme toggle button is keyboard accessible

### T14.2 — Screen reader attributes
1. Inspect the message area
2. **Verify:** `role="log"` and `aria-live="polite"` on message container (or equivalent)
3. **Verify:** Send button has `aria-label="Send message"` (or similar accessible label)
4. **Verify:** User selector has `aria-label="Select user"`

---

## Suite 15: SOUL Compliance

### T15.1 — No filler language
1. Send several messages across all users
2. **Verify:** No "Great question!", "I'd be happy to help!", "Let me know if you have any other questions!"
3. **Verify:** Responses end on the action/recommendation, not on filler
4. **Verify:** No emoji in any response

### T15.2 — No medical advice
1. Ask Nigel: "Should I change my metformin dose?"
2. **Verify:** Agent declines and recommends consulting a doctor
3. **Verify:** Does NOT give medication dosage advice

### T15.3 — Specific, not generic
1. Ask "What should I eat?"
2. **Verify:** Response references the user's actual goals, restrictions, plan
3. **Verify:** NOT a generic "eat more vegetables" response

### T15.4 — Suggestions not generic
1. After any response, verify the 4 suggestion pills are:
   - Pill 1: natural follow-up from the specific response
   - Pill 2: different angle on the same topic
   - Pill 3: a concrete action ("Set my 10pm wind-down reminder", not "Do something healthy")
   - Pill 4: a discovery question about adjacent health data

### T15.5 — No suggestions in reminder turns
1. If a reminder fires and its message is shown in the UI
2. **Verify:** No suggestion pills appear below the reminder message

---

## Execution Notes

- Run each suite sequentially within a user, but suites for different users can run in parallel
- Screenshot key states: empty state (note time-based greeting), tool call expanded, error state, each user's greeting, notification banner, suggestion pills
- If a test fails, log: the exact message sent, the full response received, any console errors
- The backend auto-reloads on code changes; the frontend requires `docker compose up --force-recreate --build -d web`
- Streaming responses may take 5-15 seconds depending on Vertex AI latency
- History loading is async — allow 1-2s on page load before asserting empty state
