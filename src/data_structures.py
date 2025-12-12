from graphviz import Digraph
import os
import textwrap

# ==========================================
# ARBRE BINAIRE (Sessions)
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
        keyword = keyword.lower()
        while stack:
            node = stack.pop()
            if keyword in node.question.lower(): return True
            if node.cause_answer and keyword in node.cause_answer.lower(): return True
            if node.right: stack.append(node.right)
            if node.left: stack.append(node.left)
        return False
    
    # --- PATH ---
    def get_visualization(self):
        """Génère la représentation textuelle de l'arbre (String)."""
        if not self.root:
            return "Arbre vide."

        lines = []
        stack = [(self.root, 0, "🌱")]
        visited_ids = set()
        MAX_NODES = 1000

        while stack:
            node, level, prefix = stack.pop()
            
            if len(lines) > MAX_NODES: break
            if id(node) in visited_ids: continue
            visited_ids.add(id(node))

            indent = "   " * level
            
            position_marker = " 📍 VOUS ÊTES ICI" if node == self.current_node else ""
            
            clean_q = node.question.replace('\n', ' ')
            if len(clean_q) > 60: clean_q = clean_q[:57] + "..."

            if node.cause_answer:
                clean_a = node.cause_answer.replace('\n', ' ')
                if len(clean_a) > 60: clean_a = clean_a[:57] + "..."
                lines.append(f"{indent}└─👤 USER: {clean_a}")

            lines.append(f"{indent}{prefix} BOT: {clean_q}{position_marker}")

            if node.right:
                stack.append((node.right, level + 1, "👉 [BRANCHE B]"))
            if node.left:
                stack.append((node.left, level + 1, "👇 [BRANCHE A]"))

        return "\n".join(lines)
    
    # --- GENERATION D'IMAGE ---
    def generate_graph_image(self, filename_base="tree_viz"):
        """
        Génère une image PNG de l'arbre avec Graphviz.
        Optimisé pour des textes longs, centrés et lisibles.
        """
        if not self.root:
            return None

        dot = Digraph(comment='Dialogue Tree', format='png', graph_attr={'dpi': '300'})
        
        dot.attr(rankdir='TB', bgcolor='#2C2F33') # Fond sombre style Discord
        
        dot.attr('node', 
            shape='box',
            style='filled,rounded',
            color='#23272A',
            fillcolor='#FFFFFF',
            fontname='Helvetica, Arial, sans-serif',
            fontsize='14',
            margin='0.3,0.1',
            height='0.6'
        )
        
        dot.attr('edge', 
            fontname='Helvetica, Arial, sans-serif',
            fontsize='12',
            color='#99AAB5',
            fontcolor='#FFFFFF'
        )

        def format_label(text, width=40):
            return "\\n".join(textwrap.wrap(text, width=width))

        stack = [self.root]
        visited_ids = set()

        while stack:
            node = stack.pop()
            node_id = str(id(node))

            if node_id in visited_ids: continue
            visited_ids.add(node_id)

            clean_q = node.question.replace('\n', ' ')
            wrapped_label = format_label(clean_q, width=40)

            fillcolor = '#FFFFFF'
            penwidth = '1'
            fontcolor = 'black'

            if node == self.current_node:
                fillcolor = '#FFCCCB'
                penwidth = '4'
                wrapped_label = "📍 VOUS ÊTES ICI\\n\\n" + wrapped_label
            elif node.is_conclusion:
                fillcolor = '#E8F5E9'

            dot.node(node_id, label=wrapped_label, fillcolor=fillcolor, penwidth=penwidth, fontcolor=fontcolor)

            if node.left:
                child_id = str(id(node.left))
                raw_label = node.left.cause_answer if node.left.cause_answer else "Start"
                edge_label = f"A: {format_label(raw_label, width=25)}"
                
                dot.edge(node_id, child_id, label=edge_label, color='#0096FF', fontcolor='#0096FF')
                stack.append(node.left)

            if node.right:
                child_id = str(id(node.right))
                raw_label = node.right.cause_answer if node.right.cause_answer else "???"
                edge_label = f"B: {format_label(raw_label, width=25)}"

                dot.edge(node_id, child_id, label=edge_label, color='#FF5733', fontcolor='#FF5733')
                stack.append(node.right)

        try:
            output_path = dot.render(filename_base, view=False, cleanup=True, renderer='cairo')
            return output_path
        except Exception as e:
            try:
                 output_path = dot.render(filename_base, view=False, cleanup=True)
                 return output_path
            except Exception as e2:
                 print(f"❌ Erreur Graphviz : {e2}")
                 return None

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
            node.cause_answer = n_data.get("a")
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