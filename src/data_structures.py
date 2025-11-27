# ==========================================
# PARTIE 1 : LISTE CHAÎNÉE (Historique)
# ==========================================

class HistoryNode:
    def __init__(self, command, author_id):
        self.command = command
        self.author_id = author_id
        self.next = None

class CommandHistory:
    def __init__(self):
        self.head = None
        self.tail = None

    def add(self, command, author_id):
        new_node = HistoryNode(command, author_id)
        if not self.head:
            self.head = new_node
            self.tail = new_node
        else:
            self.tail.next = new_node
            self.tail = new_node

    def get_last(self, author_id):
        current = self.head
        last_found = None
        while current is not None:
            if current.author_id == author_id:
                last_found = current.command
            current = current.next
        return last_found

    def get_all(self, author_id):
        result = []
        current = self.head
        while current is not None:
            if current.author_id == author_id:
                result.append(current.command)
            current = current.next
        return result

    def clear(self):
        self.head = None
        self.tail = None

    def remove_user_history(self, user_id):
        """
        Supprime tous les noeuds appartenant à un utilisateur spécifique.
        Gère la réassignation des pointeurs head et tail.
        """
        
        while self.head and self.head.author_id == user_id:
            self.head = self.head.next
            if self.head is None:
                self.tail = None
                return

        current = self.head
        while current and current.next:
            if current.next.author_id == user_id:
                current.next = current.next.next
                
                if current.next is None:
                    self.tail = current
            else:
                current = current.next

    def to_list_dict(self):
        data = []
        current = self.head
        while current is not None:
            data.append({"cmd": current.command, "user": current.author_id})
            current = current.next
        return data


# ==========================================
# PARTIE 2 : ARBRE BINAIRE (Sessions)
# ==========================================

class TreeNode:
    def __init__(self, question, is_conclusion=False):
        self.question = question
        self.user_answer = None
        self.left = None
        self.right = None
        self.is_conclusion = is_conclusion

    # --- SÉRIALISATION (Sauvegarde) ---
    def to_dict(self):
        """Transforme le noeud et ses enfants en dictionnaire récursif."""
        return {
            "q": self.question,
            "a": self.user_answer,
            "end": self.is_conclusion,
            "l": self.left.to_dict() if self.left else None,
            "r": self.right.to_dict() if self.right else None
        }

    # --- DÉSÉRIALISATION (Chargement) ---
    @staticmethod
    def from_dict(data):
        """Reconstruit un noeud (et ses enfants) depuis un dictionnaire."""
        if not data:
            return None
        
        node = TreeNode(data["q"], is_conclusion=data["end"])
        node.user_answer = data["a"]
        
        if data["l"]:
            node.left = TreeNode.from_dict(data["l"])
        if data["r"]:
            node.right = TreeNode.from_dict(data["r"])
            
        return node

class DialogueTree:
    def __init__(self):
        self.root = None
        self.current_node = None

    def reset(self):
        self.current_node = self.root

    def search_topic(self, keyword):
        return self._search_recursive(self.root, keyword.lower())

    def _search_recursive(self, node, keyword):
        if node is None: return False
        node_text = node.question.lower()
        user_text = node.user_answer.lower() if node.user_answer else ""
        if keyword in node_text or keyword in user_text: return True
        return self._search_recursive(node.left, keyword) or self._search_recursive(node.right, keyword)

    # --- SÉRIALISATION ---
    def to_dict(self):
        """Sauvegarde tout l'arbre."""
        if not self.root:
            return None
        return self.root.to_dict()

    # --- DÉSÉRIALISATION ---
    @staticmethod
    def from_dict(data):
        """Recrée un DialogueTree complet depuis les données."""
        if not data:
            return None
            
        new_tree = DialogueTree()
        new_tree.root = TreeNode.from_dict(data)

        pointer = new_tree.root
        while pointer.left:
            pointer = pointer.left
            
        new_tree.current_node = pointer
        return new_tree