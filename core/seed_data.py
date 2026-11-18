"""Hand-written synthetic seed data (plan 3.4). Every person and campus is fictional.

Campus names were checked by web search on 2026-11-18: no real institution uses them.
"""

CAMPUSES = [
    ("Larkspur State University (Demo)", "larkspur"),
    ("Cobalt Bay Institute (Demo)", "cobalt-bay"),
    ("Maple Hollow College (Demo)", "maple-hollow"),
]

# (email, first, last, campus slug, classification)
PERSONA_COOK = ("cook@larkspur.example", "Marcus", "Bell", "larkspur", "senior")
PERSONA_DINER = ("diner@larkspur.example", "Jordan", "Kim", "larkspur", "sophomore")
PERSONA_COOK2 = ("cook2@cobaltbay.example", "Elena", "Ortiz", "cobalt-bay", "junior")

OTHER_COOKS = [
    ("tess.w@larkspur.example", "Tess", "Walker", "larkspur", "junior"),
    ("omar.h@cobaltbay.example", "Omar", "Haddad", "cobalt-bay", "graduate"),
    ("lin.c@maplehollow.example", "Lin", "Chen", "maple-hollow", "senior"),
    ("dev.p@maplehollow.example", "Dev", "Patel", "maple-hollow", "sophomore"),
    ("rosa.m@larkspur.example", "Rosa", "Morales", "larkspur", "graduate"),
    ("finn.g@cobaltbay.example", "Finn", "Gallagher", "cobalt-bay", "senior"),
]

OTHER_DINERS = [
    ("sam.t@larkspur.example", "Sam", "Turner", "larkspur", "freshman"),
    ("nia.j@larkspur.example", "Nia", "Johnson", "larkspur", "junior"),
    ("leo.b@larkspur.example", "Leo", "Brooks", "larkspur", "freshman"),
    ("maya.s@cobaltbay.example", "Maya", "Singh", "cobalt-bay", "sophomore"),
    ("eli.r@cobaltbay.example", "Eli", "Ramos", "cobalt-bay", "senior"),
    ("zoe.f@cobaltbay.example", "Zoe", "Foster", "cobalt-bay", None),
    ("kai.n@maplehollow.example", "Kai", "Nguyen", "maple-hollow", "junior"),
    ("ivy.l@maplehollow.example", "Ivy", "Lopez", "maple-hollow", "freshman"),
    ("ben.a@maplehollow.example", "Ben", "Adams", "maple-hollow", "graduate"),
    ("ada.o@larkspur.example", "Ada", "Okafor", "larkspur", "senior"),
    ("max.d@cobaltbay.example", "Max", "Dubois", "cobalt-bay", "freshman"),
    ("uma.k@maplehollow.example", "Uma", "Kapoor", "maple-hollow", "sophomore"),
    ("cole.y@larkspur.example", "Cole", "Young", "larkspur", "junior"),
]

COOK_BIOS = [
    "Grew up cooking Sunday breakfast for six siblings. Pancakes are my love language.",
    "Engineering student who meal-preps like it is a lab protocol.",
    "I cook my grandmother's recipes and like having people to share them with.",
    "Vegetarian most days; happy to cook anything that brings people to the table.",
    "Learned to cook on a camp stove. Graduated to a dorm kitchen. Living the dream.",
    "Spices first, questions later.",
    "I bake when I am stressed, which during finals is a lot.",
    "Big batches, small budget: chip in for groceries and we all eat well.",
]

# Dish = (name, description, ingredients, allergens, dietary_tags)
# Eight per (meal, course): one per cook, so 48 menu items in total.
DISHES = {
    ("breakfast", "main"): [
        (
            "Buttermilk Pancakes",
            "Fluffy stack with maple syrup.",
            "flour, buttermilk, eggs, butter, maple syrup",
            ["wheat", "milk", "egg"],
            ["vegetarian"],
        ),
        (
            "French Toast",
            "Thick brioche, cinnamon and vanilla.",
            "brioche, eggs, milk, cinnamon, vanilla",
            ["wheat", "egg", "milk"],
            ["vegetarian"],
        ),
        (
            "Shakshuka",
            "Eggs poached in spiced tomato sauce.",
            "eggs, tomatoes, peppers, onion, cumin",
            ["egg"],
            ["vegetarian", "gluten_free", "dairy_free"],
        ),
        (
            "Tofu Scramble",
            "Turmeric tofu with spinach.",
            "tofu, spinach, turmeric, onion",
            ["soy"],
            ["vegan", "vegetarian", "dairy_free", "gluten_free"],
        ),
        (
            "Veggie Breakfast Burrito",
            "Eggs, black beans and peppers.",
            "tortilla, eggs, black beans, peppers, cheddar",
            ["wheat", "egg", "milk"],
            ["vegetarian"],
        ),
        (
            "Overnight Oats",
            "Oats soaked with chia and berries.",
            "oats, oat milk, chia seeds, berries",
            [],
            ["vegan", "vegetarian", "dairy_free"],
        ),
        (
            "Blueberry Waffles",
            "Crisp waffles with blueberries.",
            "flour, eggs, milk, butter, blueberries",
            ["wheat", "egg", "milk"],
            ["vegetarian"],
        ),
        (
            "Huevos Rancheros",
            "Fried eggs on tortillas with salsa.",
            "corn tortillas, eggs, black beans, salsa",
            ["egg"],
            ["vegetarian", "gluten_free", "dairy_free"],
        ),
    ],
    ("breakfast", "side"): [
        (
            "Fresh Fruit Cup",
            "Whatever is in season.",
            "melon, grapes, berries",
            [],
            ["vegan", "vegetarian", "dairy_free", "gluten_free"],
        ),
        (
            "Home Fries",
            "Crispy potatoes with onion.",
            "potatoes, onion, oil",
            [],
            ["vegan", "vegetarian", "dairy_free", "gluten_free"],
        ),
        ("Scrambled Eggs", "Soft and buttery.", "eggs, milk, butter", ["egg", "milk"], ["vegetarian", "gluten_free"]),
        ("Turkey Sausage", "Sage and black pepper.", "turkey, sage, black pepper", [], ["gluten_free", "dairy_free"]),
        ("Buttered Toast", "Sourdough, real butter.", "sourdough, butter", ["wheat", "milk"], ["vegetarian"]),
        (
            "Yogurt Parfait",
            "Yogurt, granola and honey.",
            "yogurt, granola, almonds, honey",
            ["milk", "tree_nuts"],
            ["vegetarian"],
        ),
        (
            "Hash Brown Patties",
            "Golden and crisp.",
            "potatoes, oil, salt",
            [],
            ["vegan", "vegetarian", "dairy_free", "gluten_free"],
        ),
        (
            "Cheese Grits",
            "Stone-ground grits with cheddar.",
            "grits, cheddar, butter",
            ["milk"],
            ["vegetarian", "gluten_free"],
        ),
    ],
    ("lunch", "main"): [
        (
            "Chicken Club Sandwich",
            "Triple-decker with bacon.",
            "chicken, bacon, bread, lettuce, tomato, mayonnaise",
            ["wheat", "egg"],
            [],
        ),
        (
            "Grilled Cheese",
            "Sharp cheddar on sourdough.",
            "sourdough, cheddar, butter",
            ["wheat", "milk"],
            ["vegetarian"],
        ),
        (
            "Ham and Swiss Panini",
            "Pressed with mustard.",
            "ciabatta, ham, swiss cheese, mustard",
            ["wheat", "milk"],
            [],
        ),
        (
            "Black Bean Burger",
            "House-made patty.",
            "black beans, breadcrumbs, cumin, bun, soy sauce",
            ["wheat", "soy"],
            ["vegan", "vegetarian", "dairy_free"],
        ),
        (
            "Chicken Caesar Wrap",
            "Romaine, parmesan, caesar dressing.",
            "tortilla, chicken, romaine, parmesan, anchovy",
            ["wheat", "milk", "egg", "fish"],
            [],
        ),
        (
            "Falafel Pita",
            "Crispy falafel with tahini.",
            "chickpeas, pita, tahini, cucumber",
            ["wheat", "sesame"],
            ["vegan", "vegetarian", "dairy_free"],
        ),
        (
            "Tuna Melt",
            "Open-faced and toasty.",
            "tuna, bread, cheddar, mayonnaise",
            ["fish", "wheat", "milk", "egg"],
            [],
        ),
        (
            "Veggie Fried Rice",
            "Day-old rice, done right.",
            "rice, eggs, peas, carrots, soy sauce",
            ["egg", "soy", "wheat"],
            ["vegetarian", "dairy_free"],
        ),
    ],
    ("lunch", "side"): [
        ("Tomato Soup", "Creamy and comforting.", "tomatoes, cream, basil", ["milk"], ["vegetarian", "gluten_free"]),
        (
            "Garden Salad",
            "Mixed greens, vinaigrette.",
            "lettuce, cucumber, tomato, olive oil",
            [],
            ["vegan", "vegetarian", "dairy_free", "gluten_free"],
        ),
        (
            "Potato Salad",
            "Classic picnic style.",
            "potatoes, mayonnaise, celery, mustard",
            ["egg"],
            ["vegetarian", "gluten_free", "dairy_free"],
        ),
        (
            "Sweet Potato Fries",
            "Oven-baked.",
            "sweet potatoes, oil, paprika",
            [],
            ["vegan", "vegetarian", "dairy_free", "gluten_free"],
        ),
        (
            "Coleslaw",
            "Crunchy and tangy.",
            "cabbage, carrots, mayonnaise, vinegar",
            ["egg"],
            ["vegetarian", "gluten_free", "dairy_free"],
        ),
        (
            "Hummus and Veggies",
            "Carrots, cucumbers, peppers.",
            "chickpeas, tahini, carrots, cucumber",
            ["sesame"],
            ["vegan", "vegetarian", "dairy_free", "gluten_free"],
        ),
        (
            "Chips and Salsa",
            "Fresh pico de gallo.",
            "tortilla chips, tomatoes, onion, cilantro",
            [],
            ["vegan", "vegetarian", "dairy_free", "gluten_free"],
        ),
        (
            "Lentil Soup",
            "Hearty and lemony.",
            "lentils, carrots, celery, lemon",
            [],
            ["vegan", "vegetarian", "dairy_free", "gluten_free"],
        ),
    ],
    ("dinner", "main"): [
        ("Steak Dinner", "Pan-seared with herb butter.", "sirloin, butter, garlic, thyme", ["milk"], ["gluten_free"]),
        (
            "Grilled Chicken",
            "Lemon-herb marinade.",
            "chicken, lemon, garlic, olive oil",
            [],
            ["gluten_free", "dairy_free"],
        ),
        (
            "Spaghetti and Meatballs",
            "Sunday sauce.",
            "spaghetti, beef, breadcrumbs, eggs, parmesan, tomatoes",
            ["wheat", "egg", "milk"],
            [],
        ),
        (
            "Vegetable Lasagna",
            "Layers of ricotta and roasted vegetables.",
            "lasagna noodles, ricotta, zucchini, spinach",
            ["wheat", "milk", "egg"],
            ["vegetarian"],
        ),
        (
            "Shrimp Stir-Fry",
            "Garlic, ginger and snap peas.",
            "shrimp, snap peas, soy sauce, ginger, rice",
            ["crustacean_shellfish", "soy", "wheat"],
            ["dairy_free"],
        ),
        (
            "Lentil Curry",
            "Coconut milk and warm spices.",
            "lentils, coconut milk, tomatoes, garam masala",
            [],
            ["vegan", "vegetarian", "dairy_free", "gluten_free"],
        ),
        (
            "Baked Chicken",
            "Crispy skin, juicy inside.",
            "chicken, paprika, garlic, olive oil",
            [],
            ["gluten_free", "dairy_free"],
        ),
        (
            "Salmon with Rice",
            "Teriyaki glaze.",
            "salmon, rice, soy sauce, ginger",
            ["fish", "soy", "wheat"],
            ["dairy_free"],
        ),
    ],
    ("dinner", "side"): [
        ("Baked Potato", "With butter and chives.", "potato, butter, chives", ["milk"], ["vegetarian", "gluten_free"]),
        (
            "Macaroni and Cheese",
            "Baked, with a crunchy top.",
            "macaroni, cheddar, milk, breadcrumbs",
            ["wheat", "milk"],
            ["vegetarian"],
        ),
        (
            "Collard Greens",
            "Slow-simmered.",
            "collard greens, onion, garlic, vinegar",
            [],
            ["vegan", "vegetarian", "dairy_free", "gluten_free"],
        ),
        (
            "Steamed Broccoli",
            "Lemon and sea salt.",
            "broccoli, lemon",
            [],
            ["vegan", "vegetarian", "dairy_free", "gluten_free"],
        ),
        ("Cornbread", "Skillet-baked.", "cornmeal, flour, eggs, buttermilk", ["wheat", "egg", "milk"], ["vegetarian"]),
        (
            "Roasted Carrots",
            "Honey and thyme.",
            "carrots, honey, thyme",
            [],
            ["vegetarian", "dairy_free", "gluten_free"],
        ),
        (
            "Garlic Bread",
            "Toasted with parsley.",
            "baguette, butter, garlic, parsley",
            ["wheat", "milk"],
            ["vegetarian"],
        ),
        ("Rice Pilaf", "Toasted orzo and rice.", "rice, orzo, butter, broth", ["wheat", "milk"], ["vegetarian"]),
    ],
}

BRING_LIST_ITEMS = [
    "1 lb spaghetti",
    "1 dozen eggs",
    "1 bag of salad greens",
    "2 lb potatoes",
    "1 block of cheddar",
    "1 loaf of bread",
    "1 jar of salsa",
    "1 bunch of bananas",
    "1 gallon of milk",
    "1 bag of rice",
]

REVIEW_GOOD = [
    "Generous portions and genuinely tasty.",
    "Felt like a home-cooked Sunday dinner.",
    "Everything was ready on time and still hot.",
    "The sides stole the show.",
    "Clear allergen info and friendly pickup.",
    "Best breakfast I have had on campus.",
]
REVIEW_BAD = [
    "",
    "Pickup spot was a little hard to find.",
    "Wish there had been seconds.",
    "",
    "A bit salty for my taste.",
    "",
]
