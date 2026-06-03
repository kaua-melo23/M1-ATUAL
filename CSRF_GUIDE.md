# Como usar a proteção CSRF

## Em formulários HTML

Adicione o campo oculto em **todo formulário POST**:

```html
<form method="POST" action="/admin/produtos">
  <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
  <!-- outros campos -->
  <button type="submit">Salvar</button>
</form>
```

## Em chamadas AJAX / Fetch

```javascript
// 1. Coloque o token no HTML (uma vez por página)
<meta name="csrf-token" content="{{ csrf_token() }}">

// 2. Use em todas as requisições POST/PUT/DELETE
const csrfToken = document.querySelector('meta[name="csrf-token"]').content;

fetch('/api/pedidos/1/status', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-CSRF-Token': csrfToken,           // ← obrigatório
  },
  body: JSON.stringify({ status: 'Preparando' }),
});
```

## Configuração global do Axios (se usar)

```javascript
const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
axios.defaults.headers.common['X-CSRF-Token'] = csrfToken;
```

## Em quais rotas aplicar @csrf_protect?

- **Sempre**: POST, PUT, DELETE que modificam dados
- **Não aplicar**: Login (já tem validação manual), Logout via GET (legado)
- **Não aplicar**: Webhooks externos (ex: callback do Mercado Pago — use autenticação própria)

## Exemplo de rota protegida

```python
@admin_bp.route("/produtos/<int:pid>", methods=["DELETE"])
@admin_required
@csrf_protect
def deletar_produto(pid):
    ...
```
