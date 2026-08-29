'use strict'
const original = require('prettier-plugin-jinja-template')

original.languages[0].extensions.push('.yaml')

const PLUGIN_KEY = Object.keys(original.parsers)[0]
const originalEmbed = original.printers[PLUGIN_KEY].embed
const { findPlaceholders } = require('prettier-plugin-jinja-template/lib/printer')

original.printers[PLUGIN_KEY].embed = () => {
    const origPrintFn = originalEmbed()
    return async (textToDoc, print, path, options) => {
        const node = path.getNode()
        if (!node || !['root', 'block'].includes(node.type))
            return origPrintFn(textToDoc, print, path, options)

        const ext = (options.filepath || '').split('.').pop()
        if (ext !== 'yaml')
            return origPrintFn(textToDoc, print, path, options)

        const { builders, utils } = require('prettier/doc')

        const mapped = await Promise.all(splitAtElse(node).map(async (content) => {
            let doc
            if (content in node.nodes) {
                doc = content
            }
            else if (findPlaceholders(content).length > 0) {
                doc = content
            }
            else {
                try {
                    doc = await textToDoc(content, { ...options, parser: 'yaml' })
                }
                catch (e) {
                    doc = content
                }
            }
            let ignoreDoc = false
            return utils.mapDoc(doc, (currentDoc) => {
                if (typeof currentDoc !== 'string')
                    return currentDoc
                if (currentDoc === '<!-- prettier-ignore -->') {
                    ignoreDoc = true
                    return currentDoc
                }
                const idxs = findPlaceholders(currentDoc).filter(
                    ([start, end]) => currentDoc.slice(start, end + 1) in node.nodes
                )
                if (!idxs.length) {
                    ignoreDoc = false
                    return currentDoc
                }
                const res = []
                let lastEnd = 0
                for (const [start, end] of idxs) {
                    if (lastEnd < start)
                        res.push(currentDoc.slice(lastEnd, start))
                    const p = currentDoc.slice(start, end + 1)
                    if (ignoreDoc)
                        res.push(node.nodes[p].originalText)
                    else
                        res.push(path.call(print, 'nodes', p))
                    lastEnd = end + 1
                }
                if (lastEnd > 0 && currentDoc.length > lastEnd)
                    res.push(currentDoc.slice(lastEnd))
                ignoreDoc = false
                return res
            })
        }))

        if (node.type === 'block') {
            const block = buildBlockYaml(path, print, node, mapped)
            return node.preNewLines > 1
                ? builders.group([builders.trim, builders.hardline, block])
                : block
        }
        return mapped
    }
}

function buildBlockYaml(path, print, block, mapped) {
    const { builders } = require('prettier/doc')
    if (block.content.match(/^\s*$/)) {
        return builders.fill([
            path.call(print, 'nodes', block.start.id),
            builders.softline,
            path.call(print, 'nodes', block.end.id),
        ])
    }
    return builders.group([
        path.call(print, 'nodes', block.start.id),
        mapped,
        path.call(print, 'nodes', block.end.id),
    ])
}

// ---- dup printer.js:164-173 ----
const NOT_FOUND = -1
function splitAtElse(node) {
    const elseNodes = Object.values(node.nodes).filter(
        (n) => n.type === 'statement'
            && ['else', 'elif'].includes(n.keyword)
            && node.content.search(n.id) !== NOT_FOUND
    )
    if (!elseNodes.length)
        return [node.content]
    const re = new RegExp(`(${elseNodes.map((e) => e.id).join(')|(')})`)
    return node.content.split(re).filter(Boolean)
}

module.exports = original
