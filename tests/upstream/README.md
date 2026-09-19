# Upstream formatter fixtures

The `1-unformatted-template` files preserve upstream bytes; `2-formatted-template` files
apply BioBuddies djLint and Prettier settings. Tests snapshot one pass through both tools in that
order; they do not test the parallel pre-commit scheduler. Repeated passes can still change the
wrapping of Django translation blocks, so these snapshots do not promise formatter convergence.

* Django Admin: [search_form.html, 5.2.6](https://github.com/django/django/blob/5.2.6/django/contrib/admin/templates/admin/search_form.html), [BSD-3-Clause](https://github.com/django/django/blob/5.2.6/LICENSE)
* Airflow: [_messages.html, 2.10.5](https://github.com/apache/airflow/blob/2.10.5/airflow/www/templates/airflow/_messages.html), [Apache-2.0](https://github.com/apache/airflow/blob/2.10.5/LICENSE)

The formatted copies change only formatting.
The Django fixture exercises conditional attributes, translation tags, and void elements;
the Airflow fixture exercises macros, whitespace control, and entities.
