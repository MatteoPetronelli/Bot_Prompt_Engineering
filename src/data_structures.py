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
        self.cause_answer = None
        self.left = None
        self.right = None
        self.is_conclusion = is_conclusion
        self.parent = None 

    def to_dict(self):
        return {
            "q": self.question,
            "a": self.cause_answer,
            "end": self.is_conclusion,
            "l": self.left.to_dict() if self.left else None,
            "r": self.right.to_dict() if self.right else None
        }

    @staticmethod
    def from_dict(data):
        if not data: return None
        node = TreeNode(data["q"], is_conclusion=data["end"])
        node.cause_answer = data["a"]
        
        if data["l"]:
            child = TreeNode.from_dict(data["l"])
            child.parent = node
            node.left = child
        if data["r"]:
            child = TreeNode.from_dict(data["r"])
            child.parent = node
            node.right = child
        return node

class DialogueTree:
    def __init__(self):
        self.root = None
        self.current_node = None

    def reset(self):
        self.current_node = self.root

    def search_topic(self, keyword):
        # On utilise une pile pour éviter la récursion ici aussi
        if not self.root: return False
        stack = [self.root]
        while stack:
            node = stack.pop()
            if keyword.lower() in node.question.lower(): return True
            if node.user_answer and keyword.lower() in node.user_answer.lower(): return True
            if node.right: stack.append(node.right)
            if node.left: stack.append(node.left)
        return False

    # --- SÉRIALISATION ITÉRATIVE (FLAT) ---
    def to_dict(self):
        """Transforme l'arbre en une liste plate de noeuds avec des IDs."""
        if not self.root:
            return None
        
        nodes_list = []
        queue = [self.root]
        
        node_to_id = {self.root: 0}
        next_id = 1
        
        i = 0
        while i < len(queue):
            node = queue[i]
            i += 1
            
            left_id = None
            if node.left:
                if node.left not in node_to_id:
                    node_to_id[node.left] = next_id
                    queue.append(node.left)
                    next_id += 1
                left_id = node_to_id[node.left]
                
            right_id = None
            if node.right:
                if node.right not in node_to_id:
                    node_to_id[node.right] = next_id
                    queue.append(node.right)
                    next_id += 1
                right_id = node_to_id[node.right]
            
            nodes_list.append({
                "id": node_to_id[node],
                "q": node.question,
                "a": node.cause_answer,
                "end": node.is_conclusion,
                "l_id": left_id,
                "r_id": right_id
            })
            
        return {
            "format": "flat_v1",
            "nodes": nodes_list,
            "current_id": node_to_id.get(self.current_node, 0)
        }

    # --- DÉSÉRIALISATION ITÉRATIVE ---
    @staticmethod
    def from_dict(data):
        """Reconstruit l'arbre depuis une liste plate."""
        if not data or "nodes" not in data:
            return None
            
        nodes_data = data["nodes"]
        id_to_node = {}
        
        for n_data in nodes_data:
            node = TreeNode(n_data["q"], is_conclusion=n_data["end"])
            node.cause_answer_answer = n_data["a"]
            id_to_node[n_data["id"]] = node
            
        for n_data in nodes_data:
            parent_node = id_to_node[n_data["id"]]
            
            if n_data["l_id"] is not None:
                child = id_to_node[n_data["l_id"]]
                parent_node.left = child
                child.parent = parent_node
                
            if n_data["r_id"] is not None:
                child = id_to_node[n_data["r_id"]]
                parent_node.right = child
                child.parent = parent_node
                
        new_tree = DialogueTree()
        if 0 in id_to_node:
            new_tree.root = id_to_node[0]
            
        current_id = data.get("current_id", 0)
        if current_id in id_to_node:
            new_tree.current_node = id_to_node[current_id]
        else:
            new_tree.current_node = new_tree.root
            
        return new_tree