import pygame as p

'''
Set the dimensions for the separate window and squares shown on board
'''
WIDTH = HEIGHT = 800
Dimension = 5
SquareSize = HEIGHT // Dimension

'''
This is the main function to run the whole program and generate everything needed for the UI being 
shown to the user.
'''


def main():
    p.init()
    screen = p.display.set_mode((WIDTH, HEIGHT))
    running = True
    while running:
        for e in p.event.get():
            if e.type == p.QUIT:
                running = False
        draw_board(screen)
        p.display.flip()


'''
board function which creates the colors and where to place the colors on the square blocks 
based on nested for loops
'''


def draw_board(screen):
    color = [p.Color("white"), p.Color("gray")]
    border_thickness = 3
    for r in range(Dimension):
        for c in range(Dimension):
            colors = color[((r + c) % 2)]
            # calculates the color of the current square based on the sum of the row and column,
            # alternates based on even or odd number from sum
            p.draw.rect(screen, colors, p.Rect(c * SquareSize, r * SquareSize, SquareSize, SquareSize))


if __name__ == "__main__":
    main()
