"""Story messages distinguishing provider truncation from a recoverable draft."""


def story_truncation_message(max_tokens, *, draft, reasoning):
    formatted = f"{max_tokens:,}".replace(",", " ") if max_tokens else ""
    budget = f" (budget demandé : {formatted} tokens, raisonnement compris)" if formatted else ""
    message = f"Le serveur a arrêté la réponse pour limite de longueur{budget}. "
    if draft.strip():
        return message + "Le brouillon partiel est conservé ; il doit être vérifié avant utilisation."
    message += "Aucun scénario n’a été reçu : il n’y a pas de brouillon à récupérer sans nouvel appel."
    if reasoning.strip():
        message += " Le raisonnement reçu est conservé."
    return message
