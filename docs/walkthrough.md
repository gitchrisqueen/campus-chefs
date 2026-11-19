# Walkthrough: one meal, from search to review

This page follows one booking through the app, screen by screen. It is the same story the two main browser tests play on every CI run: **E2E-01** (a diner books and the cook confirms) and **E2E-02** (after the meal, the cook closes the booking and the diner reviews it). Both tests are in [`tests/e2e/test_e2e_flows.py`](../tests/e2e/test_e2e_flows.py).

Every picture is an unedited 1120 x 700 screen of the seeded demo, captured by `scripts/capture_screenshots.py --walkthrough`. The dates in them are relative to the day they were captured. To follow along yourself, run `make demo` and open <http://127.0.0.1:8000> ([README, "Run the demo"](../README.md#run-the-demo)).

The two people are seeded demo accounts. **Jordan K.** is the demo diner. **Marcus B.** is the demo cook. Neither has a password: you log in with the "Try as demo diner" and "Try as demo cook" buttons. Use two browser profiles, or one normal and one private window, to be both at once.

## Part 1: book a seat (E2E-01)

### 1. Start on the home page

The home page says what the app does and shows an example listing. The yellow banner at the top is on every page of the demo.

![Home page: the banner "Portfolio demo: fictional people and campuses", the headline "Home-cooked meals, made by students who love to cook", the Find a meal and How it works buttons, and an example listing for Buttermilk Pancakes.](screenshots/walkthrough/01-home.png)

### 2. Search for a dish

Log in as the demo diner and type `pancakes` into the search box. The results appear under the box as you type. The server returns just the results, and htmx puts them on the page. With JavaScript off, the Search button loads the same results as a full page (E2E-05).

![The Find a meal box with "pancakes" typed in. Under it, a note that allergens are declared by each cook, the line "1 meal matches pancakes", and a card for Pancake Breakfast by Marcus B. with a $4.00 grocery share per seat.](screenshots/walkthrough/02-search.png)

### 3. Open the meal

The meal page lists each dish with the allergens and dietary tags the cook declared, then when and where the meal is, and how many seats are left.

![Pancake Breakfast by Marcus B. at Larkspur State University (Demo). Dishes: Buttermilk Pancakes, which contains wheat, milk and egg, and Fresh Fruit Cup, with no major allergens declared. On the right: breakfast, the serving time, when requests close, 4 of 6 seats left, pickup.](screenshots/walkthrough/03-offering.png)

### 4. Choose how to chip in

This meal's groceries cost $24.00 and it has six seats, so the cook set the share at $4.00 a seat. The diner can pay that share, bring an item from the bring list instead, or propose other terms. The request cannot be sent until the allergen box is ticked (BOOK-02).

![The Chip in section, showing $4.00 grocery share per seat or bring an item, and the bring list of salsa and bananas. Beside it the Request seats form: 1 seat, "Grocery share: $4.00 per seat, paid to the cook in person" selected, and the box "I have read the allergens" ticked.](screenshots/walkthrough/04-form.png)

### 5. Send the request

Press **Request seats**. The form is replaced in place by a confirmation, and the share is fixed at the amount shown. If the cook edits the meal later, this booking keeps its $4.00 (CONTRIB-03).

![The Request seats panel now reads "Request sent. The cook will confirm or decline it." and "Grocery share: $4.00, pay the cook in person", with a View your booking button.](screenshots/walkthrough/05-request-sent.png)

### 6. The cook sees the request

In the other window, log in as the demo cook and open the booking from the account page. The cook sees who asked, for how many seats, and what they offered to chip in. The cook can confirm, decline or cancel.

![The cook's view of the booking: status Requested, "Jordan K. asked for 1 seat at your meal", the grocery share of $4.00, the timeline, and a "What you can do" card with Confirm, Decline and Cancel booking.](screenshots/walkthrough/06-cook-sees-request.png)

### 7. The cook confirms

Press **Confirm**. Before it confirms, the app locks the meal's row and counts the confirmed seats again, so two confirmations at the same moment cannot overbook the meal (`bookings/services.py`). The cook now has a "Mark contribution received" button for later.

![The same booking after confirming: a green message "Booking confirmed", status Confirmed, and a Mark contribution received button under the $4.00 grocery share.](screenshots/walkthrough/07-cook-confirmed.png)

### 8. The diner sees the confirmation

Back in the diner's window, the booking is confirmed. The page says what to pay and that it is paid in person. A confirmed diner now also sees the cook's pickup note, which is hidden from everyone else (BOOK-14).

![The diner's booking: status Confirmed, "1 seat with Marcus B.", "Grocery share: $4.00, pay the cook in person", "Not marked received yet. Money changes hands in person; nothing is paid on this site", a timeline with Requested and Confirmed, and the pickup note.](screenshots/walkthrough/08-diner-confirmed.png)

That is the end of E2E-01. The test asserts the "Request sent" text, the cook's "Booking confirmed" message, the Confirmed badge on the diner's page and the exact contribution line.

## Part 2: after the meal (E2E-02)

A booking can be completed only after the meal's serving time, so this part uses a booking that is already in the seed: Jordan's confirmed seat at Marcus's **Steak Night**, served yesterday.

### 9. The cook opens yesterday's booking

As the demo cook, open Steak Night from the kitchen's past meals and pick Jordan's booking. The share has not been marked received.

![The cook's view of the Steak Night booking: status Confirmed, "Grocery share: $4.00, pay the cook in person", "Not marked received yet", and a Mark contribution received button.](screenshots/walkthrough/09-cook-after-the-meal.png)

### 10. Mark the share received

Press **Mark contribution received**. This records the time. It is a field beside the booking's status, not a new status, and only the cook can set it (CONTRIB-07).

![A green message "Contribution marked received". The Chip in card now reads "Grocery share: $4.00" and "Received by the cook" with the date and time.](screenshots/walkthrough/10-share-received.png)

### 11. Mark the booking completed

Press **Mark completed** in the "What you can do" card. Completing is allowed only after the serving time (BOOK-11).

![A green message "Booking marked completed" and the status Completed on the Steak Night booking.](screenshots/walkthrough/11-completed.png)

### 12. The diner writes a review

As the demo diner, open the same booking. A completed booking shows a review form for 14 days (REV-05). A review is a rating from 1 to 5 and two optional parts, "The good" and "The bad".

![The review form: five rating choices with "5 stars" selected, "The good" filled with "Steak cooked just right, and the herb butter was great", "The bad" filled with "Pickup ran ten minutes late", and a Post review button.](screenshots/walkthrough/12-review-form.png)

### 13. The review is posted

Press **Post review**. A booking can be reviewed once (REV-03).

![A green message "Thanks, your review is posted" above the completed Steak Night booking.](screenshots/walkthrough/13-review-posted.png)

### 14. The review is on the cook's page

Follow the cook's name to their public page. The review is listed with the diner's first name and initial, the meal and the date, and it now counts in the cook's average (REV-01).

![The Reviews section of Marcus B.'s page: "5 out of 5", "Jordan K., Steak Night", then "The good: Steak cooked just right, and the herb butter was great" and "The bad: Pickup ran ten minutes late".](screenshots/walkthrough/14-review-on-cook-page.png)

That is the end of E2E-02. The test asserts both of the cook's messages, the Completed badge, the "review is posted" message, and that the cook's page lists the review text exactly once with "5 out of 5".

## Run the two tests

`make e2e` reseeds the demo data and runs every browser test. To run only these two:

```sh
make e2e K="e2e_01 or e2e_02"
```

The last line reads `2 passed, 356 deselected` and a time.

After clicking through by hand, run `make reseed` to put the demo data back. `make screenshots` does that for you when it recaptures these pictures.
