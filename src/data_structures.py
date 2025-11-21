# data_structures.py

# --- STRUCTURE 1 : LISTE CHAÎNÉE (Pour l'historique des commandes) ---
class HistoryNode:
    def __init__(self, command, author_id):
        self.command = command
        self.author_id = author_id
        self.next = None

class CommandHistory:
    def __init__(self):
        self.head = None
        self.tail = None # Optimisation pour ajout rapide à la fin

    def add(self, command, author_id):
        new_node = HistoryNode(command, author_id)
        if not self.head:
            self.head = new_node
            self.tail = new_node
        else:
            self.tail.next = new_node
            self.tail = new_node

    def get_last(self, author_id):
        # Parcours pour trouver le dernier (complexité O(n) car liste simple)
        current = self.head
        last_cmd = None
        while current:
            if current.author_id == author_id:
                last_cmd = current.command
            current = current.next
        return last_cmd

    def get_all(self, author_id):
        # Retourne une liste python juste pour l'affichage
        cmds = []
        current = self.head
        while current:
            if current.author_id == author_id:
                cmds.append(current.command)
            current = current.next
        return cmds

    def clear(self):
        self.head = None
        self.tail = None

    # Pour la sauvegarde JSON
    def to_list_dict(self):
        data = []
        current = self.head
        while current:
            data.append({"cmd": current.command, "user": current.author_id})
            current = current.next
        return data

# --- STRUCTURE 2 : ARBRE BINAIRE DYNAMIQUE (Pour la discussion) ---
class TreeNode:
    def __init__(self, question, is_root=False):
        self.question = question      # La question posée par le bot
        self.user_answer = None       # La réponse donnée par l'user pour arriver ici
        self.left = None              # Branche "Non" ou "Option A"
        self.right = None             # Branche "Oui" ou "Option B"
        self.is_conclusion = False    # Si True, c'est le résultat final

    def to_dict(self):
        # Récursif pour le JSON
        return {
            "question": self.question,
            "answer": self.user_answer,
            "left": self.left.to_dict() if self.left else None,
            "right": self.right.to_dict() if self.right else None,
            "is_conclusion": self.is_conclusion
        }

class DialogueTree:
    def __init__(self):
        self.root = None
        self.current_node = None # Pointeur vers où en est l'utilisateur

    def reset(self):
        self.current_node = self.root

    # Fonctionnalité demandée : "speak about X" (Recherche dans l'arbre)
    def search_topic(self, topic, node=None):
        if node is None:
            node = self.root
        if node is None:
            return False

        # Vérifie si le sujet est dans la question ou la réponse stockée
        if topic.lower() in node.question.lower() or (node.user_answer and topic.lower() in node.user_answer.lower()):
            return True
        
        # Recherche récursive à gauche puis à droite
        found_left = self.search_topic(topic, node.left)
        if found_left: return True
        
        return self.search_topic(topic, node.right)
