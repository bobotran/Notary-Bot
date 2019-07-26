# Adapted from nickstanisha/trie.py --> https://gist.github.com/nickstanisha/733c134a0171a00f66d4
import pdb

class Node:
    def __init__(self, label=None, data=None, val=None):
        self.label = label
        self.data = data
        self.val = val
        self.children = dict()

    def addChild(self, key, data=None, val=None):
        if not isinstance(key, Node):
            self.children[key] = Node(key, data, val)
        else:
            self.children[key.label] = key

    def __getitem__(self, key):
        return self.children[key]

class Trie:
    def __init__(self, word_list=[]):
        '''
        Inserts the elements in word_list into the Trie, with the word as the key
        and the index of the word + 1 as the value.
        '''
        self.head = Node()

        for idx in range(len(word_list)):
            self.add(word_list[idx], idx + 1)

    def __getitem__(self, key):
        return self.head.children[key]

    def add(self, word, value=None):
        current_node = self.head
        word_finished = True

        for i in range(len(word)):
            if word[i] in current_node.children:
                current_node = current_node.children[word[i]]
            else:
                word_finished = False
                break

        # For ever new letter, create a new child node
        if not word_finished:
            while i < len(word):
                current_node.addChild(word[i])
                current_node = current_node.children[word[i]]
                i += 1

        # Let's store the full word at the end node so we don't need to
        # travel back up the tree to reconstruct the word
        current_node.data = word
        current_node.val = value
    def has_word(self, word):
        if word == '':
            return False
        if word == None:
            raise ValueError('Trie.has_word requires a not-Null string')

        # Start at the top
        current_node = self.head
        exists = True
        for letter in word:
            if letter in current_node.children:
                current_node = current_node.children[letter]
            else:
                exists = False
                break

        # Still need to check if we just reached a word like 't'
        # that isn't actually a full word in our dictionary
        if exists:
            if current_node.data == None:
                exists = False

        return exists

    def start_with_prefix(self, prefix):
        """ Returns a list of all nodes in tree that start with prefix """
        nodes = list()
        if prefix == None:
            raise ValueError('Requires not-Null prefix')

        # Determine end-of-prefix node
        top_node = self.head
        for letter in prefix:
            if letter in top_node.children:
                top_node = top_node.children[letter]
            else:
                # Prefix not in tree, go no further
                return nodes

        # Get words under prefix
        if top_node == self.head:
            queue = [node for key, node in top_node.children.items()]
        else:
            queue = [top_node]

        # Perform a breadth first search under the prefix
        # A cool effect of using BFS as opposed to DFS is that BFS will return
        # a list of words ordered by increasing length
        while queue:
            current_node = queue.pop()
            if current_node.data != None:
                # Isn't it nice to not have to go back up the tree?
                nodes.append(current_node)

            queue = [node for key,node in current_node.children.items()] + queue

        return nodes

    # def get_val(self, word):
    #     """ This returns the 'val' of the node identified by the given word """
    #     if not self.has_word(word):
    #         raise ValueError('{} not found in trie'.format(word))
    #
    #     # Race to the bottom, get data
    #     current_node = self.head
    #     for letter in word:
    #         current_node = current_node[letter]
    #
    #     return current_node.val
