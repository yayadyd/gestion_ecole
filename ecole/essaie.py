from ecole.cycles import classes_du_cycle
print('1er cycle :')
for c in classes_du_cycle('1er'):
    print(f'  - {c.nomClasse}')
print()
print('2e cycle :')
for c in classes_du_cycle('2e'):
    print(f'  - {c.nomClasse}')
