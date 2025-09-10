SUIT_EMOJIS = {
    "Hearts": "♥️",
    "Diamonds": "♦️",
    "Clubs": "♣️",
    "Spades": "♠️"
}


def format_card_emoji(card, is_passed=False, is_selected=False):
    #Format a card with emoji and appropriate styling
    emoji = SUIT_EMOJIS[card.suit]
    base_text = f"{card.rank}{emoji}"

    if is_selected:
        return f"✓ {base_text}"  # Checkmark + bold for selected
    elif is_passed:
        return f"**{base_text}**"  # Bold for passed cards
    else:
        return base_text  # Normal for regular cards


def format_card_list(cards, passed_cards=None, selected_cards=None):
    #Format a list of cards with appropriate styling
    if passed_cards is None:
        passed_cards = []
    if selected_cards is None:
        selected_cards = []

    formatted_cards = []
    for card in cards:
        is_passed = card in passed_cards
        is_selected = card in selected_cards
        formatted_cards.append(format_card_emoji(card, is_passed, is_selected))

    return ", ".join(formatted_cards)