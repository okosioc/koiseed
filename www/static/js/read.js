//
// Js functions to install components in a reading-model-page.
//

function install_read() {
    // fancybox
    // https://fancyapps.com/fancybox/getting-started/
    if (window["Fancybox"]) {
        Fancybox.bind("[data-fancybox]", {
            //
        });
    }

    // editorjs
    // https://github.com/codex-team/editor.js
    $(".editorjs").each(function (i, n) {
        var id = $(n).attr("id"),
            content = $(n).next(":hidden").val();
        var editor = new EditorJS({
            holder: id,
            tools: {
                header: Header,
                image: ImageTool,
                list: NestedList,
                code: CodeTool,
                quote: Quote,
                delimiter: Delimiter,
                table: Table,
            },
            readOnly: true,
            data: content ? JSON.parse(content) : {},
        });
    });
}