# Relatório intermediário

O documento principal é `root.tex`, formatado com a classe `ppgccufmg` do [template de propostas, dissertações e teses do PPGCC/UFMG](https://github.com/UFMG-Organizacao-de-Disciplinas/Templates-propostas_dissertacoes_teses). A cópia da classe e sua licença estão nesta pasta para compilação independente. O texto foi condensado e usa espaçamentos reduzidos para respeitar o limite de cinco páginas; confirme a paginação final após inserir os nomes.

Os metadados do discente e orientador devem ser preenchidos em `root.tex`. O documento usa a opção `mscproposta` e a capa da classe. Para respeitar o limite de cinco páginas do relatório, não inclui os elementos pré-textuais completos de uma dissertação (folha de rosto, resumo, abstract e sumário).

Compile nesta pasta com:

```sh
pdflatex root.tex
bibtex root
pdflatex root.tex
pdflatex root.tex
```
