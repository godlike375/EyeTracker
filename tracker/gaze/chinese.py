import numpy


class Graph:
    def __init__(self, vertices, edges):
        self.vertices = vertices
        self.edges = edges
        self.adj_list = {v: [] for v in vertices}
        for edge in edges:
            self.adj_list[edge[0]].append(edge[1])
            self.adj_list[edge[1]].append(edge[0])

    def get_odd_degree_vertices(self):
        return [v for v in self.vertices if len(self.adj_list[v]) % 2 != 0]

    def add_edge(self, u, v):
        self.edges.append((u, v))
        self.adj_list[u].append(v)
        self.adj_list[v].append(u)

def add_edges_to_make_eulerian(graph):
    odd_vertices = graph.get_odd_degree_vertices()

    if len(odd_vertices) % 2 != 0:
        raise ValueError("Граф не может содержать нечётное число вершин с нечётной степенью")

    while odd_vertices:
        u = odd_vertices.pop()
        v = odd_vertices.pop()
        graph.add_edge(u, v)

def find_eulerian_circuit(graph):
    stack = [next(iter(graph.vertices))]
    path = []

    while stack:
        current = stack[-1]
        if graph.adj_list[current]:
            next_vertex = graph.adj_list[current].pop()
            graph.adj_list[next_vertex].remove(current)
            stack.append(next_vertex)
        else:
            path.append(stack.pop())

    return path


vertices = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]

def block_to_edges(block):
    lt, rt, rb, lb, c = block
    return tuple(sorted([lt, rt])), tuple(sorted([rt, rb])), tuple(sorted([rb, lb])),\
           tuple(sorted([lb, lt])), tuple(sorted([lt, c])), tuple(sorted([rt, c])),\
           tuple(sorted([rb, c])), tuple(sorted([lb, c]))


blocks = [
    (1, 2, 13, 8, 9),
    (2, 3, 4, 13, 10),
    (13, 4, 5, 6, 11),
    (8, 13, 6, 7, 12),
    ]

def flatten_comprehension(matrix):
    return [item for row in matrix for item in row]

edges = list(set(flatten_comprehension(block_to_edges(block) for block in blocks)))


graph = Graph(vertices, edges)
add_edges_to_make_eulerian(graph)
eulerian_circuit = find_eulerian_circuit(graph)

print("Эйлеров цикл:", eulerian_circuit)


a = []
a[:] = 1,2,3,4
print(a)

