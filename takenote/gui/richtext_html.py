"""
  HTML reader/writer for RichText
"""


# python imports
import re
from HTMLParser import HTMLParser

# takenote imports
from takenote.gui.textbuffer_tools import \
     iter_buffer_contents, \
     buffer_contents_iter_to_offset, \
     normalize_tags, \
     insert_buffer_contents, \
     buffer_contents_apply_tags, \
     TextBufferDom, \
     TextDom, \
     AnchorDom, \
     TagDom, \
     TagNameDom


from takenote.gui.richtextbuffer import \
     IGNORE_TAGS, \
     add_child_to_buffer, \
     RichTextBuffer, \
     RichTextImage, \
     RichTextHorizontalRule, \
     RichTextError, \
     RichTextTag, \
     RichTextModTag, \
     RichTextFamilyTag, \
     RichTextSizeTag, \
     RichTextJustifyTag, \
     RichTextFGColorTag, \
     RichTextBGColorTag, \
     RichTextIndentTag, \
     RichTextBulletTag




# constants
XHTML_HEADER = """<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<body>"""
XHTML_FOOTER = "</body></html>"

BULLET_STR = u"\u2022 "


def nest_indent_tags(contents, tag_table):
    """Convert indent tags so that they nest like HTML tags"""

    indent = 0
    indent_closing = False

    # loop through contents stream
    for item in contents:
        
        # if we are in the middle of a indent closing event, then the next
        # item determines what we should do
        if indent_closing:
            if item[0] == "anchor" or item[0] == "text":            
                # if we see "content" (anchors or text) (instead of
                # immediately opening a new indent) then we must close all
                # indents (i.e. indent=0)
                while indent > 0:
                    yield ("end", None, tag_table.lookup(
                        RichTextIndentTag.tag_name(indent)))
                    indent -= 1
                indent_closing = False

            elif item[0] == "begin":
                # if we see a begining tag then check to see if its an
                # indentation tag
                tag = item[2]
                
                if isinstance(tag, RichTextIndentTag):
                    # (A) if it is a new indentation  that is of lower indent
                    # close all indents until we match
                    next_indent = tag.get_indent()

                    while indent > next_indent:
                        yield ("end", None, tag_table.lookup(
                            RichTextIndentTag.tag_name(indent)))
                        indent -= 1
                
                    indent_closing = False
            else:
                # do nothing
                pass

        # yield items
        if item[0] == "begin" and \
           isinstance(item[2], RichTextIndentTag):
                # if item is a begining indent, open indents until we match
                tag = item[2]
                next_indent = tag.get_indent()

                # should be true since (A) should have executed
                assert next_indent >= indent
                
                while indent < next_indent:
                    # open new indents until we match level
                    indent += 1
                    assert indent > 0
                    yield ("begin", None, tag_table.lookup(
                        RichTextIndentTag.tag_name(indent)))

        elif item[0] == "end" and \
             isinstance(item[2], RichTextIndentTag):
                next_indent = item[2].get_indent()
                indent_closing = True
        else:
            yield item

    # close all remaining indents
    while indent > 0:
        yield ("end", None, tag_table.lookup(
            RichTextIndentTag.tag_name(indent)))
        indent -= 1


def unnest_indent_tags(contents):
    """Convert nested indents to unnested"""

    indent = 0       # level of indent
    li_stack = []    # stack of open indents

    for item in contents:            
        kind, pos, param = item

        if kind == "beginstr":
            if param == "ol":
                # increase indent
                indent += 1

            elif param.startswith("li"):
                # close open indents
                if len(li_stack) > 0:
                    yield ("endstr", None, li_stack[-1])

                # start new indent
                par_type = param[3:]
                tagstr = "indent %d %s" % (indent, par_type)
                yield ("beginstr", None, tagstr)
                li_stack.append(tagstr)

                # add bullet points if needed
                if par_type == "bullet":
                    yield ("beginstr", None, "bullet")
                    yield ("text", None, BULLET_STR)
                    yield ("endstr", None, "bullet")
            else:
                yield item

        elif kind == "endstr":
            if param == "ol":
                # decrease indent
                indent -= 1

            elif param.startswith("li"):
                # stop indent
                par_type = param[3:]
                li_stack.pop()
                yield ("endstr", None,
                       "indent %d %s" % (indent, par_type))

                # resume previous indent
                if len(li_stack) > 0:
                    yield ("beginstr", None, li_stack[-1])

            else:
                yield item

        else:
                yield item
                

def find_paragraphs(contents):
    """Wrap each paragraph with a pair of tags"""

    within_par = False

    others = []
    par_type = "none"

    pars = {"none": P_TAG,
            "bullet": P_BULLET_TAG}
    par_stack = []

    for item in contents:

        if item[0] == "text":

            for item2 in others:                
                yield item2
            others = []
            
            if not within_par:
                # starting paragraph
                within_par = True
                yield ("begin", None, pars[par_type])
                par_stack.append(pars[par_type])

            text = item[2]
            i = 0
            for j, c in enumerate(text):
                if not within_par:
                    within_par = True
                    yield ("begin", None, pars[par_type])
                    par_stack.append(pars[par_type])
                
                if c == "\n":
                    yield ("text", None, text[i:j+1])
                    yield ("end", None, par_stack.pop())
                    within_par = False
                    i = j+1

            # yield remaining text
            if i < j+1:
                if not within_par:
                    within_par = True
                    yield ("begin", None, pars[par_type])
                    par_stack.append(pars[par_type])
                yield ("text", None, text[i:j+1])

        elif item[0] == "anchor":

            for item2 in others:
                yield item2
            others = []
            
            if not within_par:
                # starting paragraph
                within_par = True
                yield ("begin", None, pars[par_type])
                par_stack.append(pars[par_type])

            # yield anchor
            yield item
            
        
        else:
            # pass other items through

            if item[0] == "begin" and \
               isinstance(item[2], RichTextIndentTag):
                par_type = item[2].get_par_indent()
            
            others.append(item)

    if within_par:
        yield ("end", None, par_stack.pop())
    
    for item in others:
        yield item


        

class HtmlTagDom (TagDom):
    def __init__(self, tag):
        TagDom.__init__(self, tag)

class RichTextParTag (RichTextTag):
    def __init__(self, kind):
        RichTextTag.__init__(self, "p")
        self.kind = kind

LI_TAG = RichTextTag("li")
P_TAG = RichTextParTag("none")
P_BULLET_TAG = RichTextParTag("bullet")

class LiHtmlTagDom (HtmlTagDom):
    def __init__(self, kind):
        HtmlTagDom.__init__(self, LI_TAG)
        self.kind = kind

class HtmlError (StandardError):
    """Error for HTML parsing"""
    pass


# TODO: may need to include support for ignoring information between
# <scirpt> and <style> tags

class HtmlBuffer (HTMLParser):
    """Read and write HTML for a RichTextBuffer"""
    
    def __init__(self, out=None):
        HTMLParser.__init__(self)
    
        self._out = out
        self._mod_tags = "biu"
        self._html2buffer_tag = {
            "b": "bold",
            "i": "italic",
            "u": "underline",
            "nobr": "nowrap"}
        self._buffer_tag2html = {
            "bold": "b",
            "italic": "i",
            "underline": "u",
            "nowrap": "nobr"
            }
        self._justify = set([
            "left",
            "center",
            "right",
            "fill",
            "justify"])
        self._newline = False

        self._tag_stack = []
        self._butter_contents = []
        self._text_queue = []
        self._within_body = False
        self._partial = False
        self._indent = 0
        
        self._entity_char_map = [("&", "amp"),
                                (">", "gt"),
                                ("<", "lt"),
                                (" ", "nbsp")]
        self._entity2char = {}
        for ch, name in self._entity_char_map:
            self._entity2char[name] = ch
        
        self._charref2char = {"09": "\t"}
        
        
        
    
    def set_output(self, out):
        """Set the output stream for HTML"""
        self._out = out


    #===========================================
    # Reading HTML
    
    def read(self, infile, partial=False, ignore_errors=False):
        """Read from stream infile to populate textbuffer"""
        #self._text_queue = []
        self._within_body = False
        self._partial = partial
        
        self._dom = TextBufferDom()
        self._dom_ptr = self._dom
        self._tag_stack = [(None, self._dom)]

        try:
            for line in infile:
                self.feed(line)                
            self.close()
            
        except Exception, e:
            # reraise error if not ignored
            if not ignore_errors:
                raise
        
        self.process_dom_read(self._dom)
        return unnest_indent_tags(self._dom.get_contents())


    def process_dom_read(self, dom):
        """Process a DOM after reading"""

        def walk(node):

            if isinstance(node, TagNameDom) and node.tagname == "ol":
                # new lists imply newline if it has a previous sibling
                if node.prev_sibling():
                    node.get_parent().insert_before(node, TextDom("\n"))
            
            if isinstance(node, TagNameDom) and node.tagname.startswith("li"):
                # list items end with an implied newline

                if not (isinstance(node.last_child(), TagNameDom) and \
                        node.last_child().tagname == "ol"):
                    node.append_child(TextDom("\n"))
            
            for child in list(node):
                walk(child)
        walk(dom)

    
    def append_text(self, text):
        if len(text) > 0:
            last_child = self._dom_ptr.last_child()
            if isinstance(last_child, TextDom):
                last_child.text += text
            else:
                self._dom_ptr.append_child(TextDom(text))


    def parse_style(self, stylestr):
        """Parse a style attribute"""

        # TODO: this parsing may be too simplistic
        for statement in stylestr.split(";"):
            statement = statement.strip()
            
            tagstr = None
        
            if statement.startswith("font-size"):
                # font size
                size = int("".join(filter(lambda x: x.isdigit(),
                                   statement.split(":")[1])))
                tagstr = "size " + str(size)
                        
            elif statement.startswith("font-family"):
                # font family
                tagstr = "family " + statement.split(":")[1].strip()

                
            elif statement.startswith("text-align"):
                # text justification
                align = statement.split(":")[1].strip()
                
                if align not in self._justify:
                    raise HtmlError("unknown justification '%s'" % align)

                if align == "justify":
                    tagstr = "fill"
                else:
                    tagstr = align

            elif statement.startswith("color"):
                # foreground color
                fg_color = statement.split(":")[1].strip()
                
                if fg_color.startswith("#"):
                    if len(fg_color) == 4:
                        x, a, b, c = fg_color
                        fg_color = x + a + a + b + b+ c + c
                        
                    if len(fg_color) == 7:
                        tagstr = "fg_color " + fg_color

            elif statement.startswith("background-color"):
                # background color
                bg_color = statement.split(":")[1].strip()
                
                if bg_color.startswith("#"):
                    if len(bg_color) == 4:
                        x, a, b, c = bg_color
                        bg_color = x + a + a + b + b+ c + c
                        
                    if len(bg_color) == 7:
                        tagstr = "bg_color " + bg_color

            else:
                # ignore other styles
                pass

        
            if tagstr is not None:
                tag = TagNameDom(tagstr)
                self._dom_ptr.append_child(tag)
                self._dom_ptr = tag


    def parse_image(self, attrs):
        """Parse image tag and return image child anchor"""
        
        img = RichTextImage()
        width, height = None, None
            
        for key, value in attrs:
            if key == "src":
                img.set_filename(value)
                    
            elif key == "width":
                try:
                    width = int(value)
                except ValueError, e:
                    # ignore width if we cannot parse it
                    pass
                
            elif key == "height":
                try:
                    height = int(value)
                except ValueError, e:
                    # ignore height if we cannot parse it
                    pass
                
            else:
                # ignore other attributes
                pass
            

        img.scale(width, height)
        return img
        
    
    def handle_starttag(self, htmltag, attrs):
        """Callback for parsing a starting HTML tag"""
        
        self._newline = False

        # start a new tag on htmltag stack
        self._tag_stack.append((htmltag, self._dom_ptr))


        if htmltag == "html":
            # ignore html tag
            pass
        
        elif htmltag == "body":
            # note that we are within the body tag
            self._within_body = True

        
        elif htmltag in self._html2buffer_tag:
            # simple font modifications (b/i/u)
            
            tagstr = self._html2buffer_tag[htmltag]
            tag = TagNameDom(tagstr)
            self._dom_ptr.append_child(tag)
            self._dom_ptr = tag

        elif htmltag == "span":
            # apply style
            
            for key, value in attrs:
                if key == "style":
                    self.parse_style(value)
                else:
                    # ignore other attributes
                    pass
        
        elif htmltag == "div":
            # text justification
            
            for key, value in attrs:
                if key == "style":
                    self.parse_style(value)
                else:
                    # ignore other attributes
                    pass

        elif htmltag == "p":
            # paragraph
            # NOTE: this tag is currently not used by TakeNote, but if pasting
            # text from another HTML source, TakeNote will interpret it as
            # a newline char
            self.append_text("\n")
            
        elif htmltag == "br":
            # insert newline
            self.append_text("\n")
            self._newline = True
            
        elif htmltag == "hr":
            # horizontal break
            hr = RichTextHorizontalRule()
            self.append_text("\n")
            self._dom_ptr.append_child(AnchorDom(hr))
            self.append_text("\n")
    
        elif htmltag == "img":
            # insert image
            img = self.parse_image(attrs)
            self._dom_ptr.append_child(AnchorDom(img))

        elif htmltag == "ul" or htmltag == "ol":
            # indent
            tag = TagNameDom("ol")
            self._dom_ptr.append_child(tag)
            self._dom_ptr = tag
            
        elif htmltag == "li":            
            par_type = "none"

            for key, value in attrs:
                if key == "style":
                    for statement in value.split(";"):
                        key2, value2 = statement.split(":")
                        value2 = value2.strip()
                        
                        if key2.strip() == "list-style-type":
                            if value2 == "disc":
                                par_type = "bullet"

            tag = TagNameDom("li %s" % par_type)
            self._dom_ptr.append_child(tag)
            self._dom_ptr = tag

        else:
            # ingore other html tags
            pass
        
        

    def handle_endtag(self, htmltag):
        """Callback for parsing a ending HTML tag"""


        if not self._partial:
            if htmltag in ("html", "body") or not self._within_body:
                return

        # keep track of newline status
        if htmltag != "br":
            self._newline = False
        
        if htmltag == "ul" or htmltag == "ol" or htmltag == "li":
            self._newline = True
        
        elif htmltag == "p":
            # paragraph tag
            self.append_text("\n")


        # pop dom stack
        if len(self._tag_stack) == 0:
            return
        else:
            htmltag2, self._dom_ptr = self._tag_stack.pop()
            while len(self._tag_stack) > 0 and htmltag2 != htmltag:
                htmltag2, self._dom_ptr = self._tag_stack.pop()

    
    
    def handle_data(self, data):
        """Callback for character data"""

        if not self._partial and not self._within_body:
            return

        if self._newline:
            data = re.sub("^\n[\n ]*", "", data)
            data = re.sub("[\n ]+", " ", data)
            self._newline = False
        else:
            data = re.sub("[\n ]+", " ", data)
        
        if len(data) > 0:
            self.append_text(data)

    
    def handle_entityref(self, name):
        """Callback for reading entityref"""
        if not self._partial and not self._within_body:
            return
        self.append_text(self._entity2char.get(name, ""))
    
    
    def handle_charref(self, name):
        """Callback for reading charref"""
        if not self._partial and not self._within_body:
            return
        self.append_text(self._charref2char.get(name, ""))



    #================================================
    # Writing HTML

    def write(self, buffer_content, tag_table, partial=False):

        if not partial:
            self._out.write(XHTML_HEADER)

        # normalize contents, prepare them for DOM
        contents = normalize_tags(
            nest_indent_tags(find_paragraphs(buffer_content), tag_table),
            is_stable_tag=lambda tag:
                isinstance(tag, (RichTextIndentTag, RichTextParTag)))
        
        dom = TextBufferDom(contents)
        self.prepare_dom_write(dom)
        self.write_dom(dom)

        if not partial:
            self._out.write(XHTML_FOOTER)


    def prepare_dom_write(self, dom):
        """Prepare a DOM for writing"""
        
        # (1) change all <p> tags to li, if inside indent
        # (2) else remove <p>
        # (3) insert <li> above <ol>
        def walk(node, within_indent, par_type):
            if isinstance(node, TagDom):
                if isinstance(node.tag, RichTextParTag):
                    
                    if within_indent:
                        # (1) change p to li
                        item_dom = LiHtmlTagDom(node.tag.kind)

                        # move all children of p to li
                        while True:                        
                            child = node.first_child()
                            if not child:
                                break
                            child.remove()
                            item_dom.append_child(child)

                        parent = node.get_parent()
                        parent.replace_child(node, item_dom)
                        return

                    else:
                        # (2) remove p
                        parent = node.get_parent()

                        # move all children of p to p.parent
                        while True:                        
                            child = node.first_child()
                            if not child:
                                break
                            child.remove()
                            parent.insert_before(node, child)
                        node.remove()
                            
                # (3) insert li above ol
                elif isinstance(node.tag, RichTextIndentTag):
                    if within_indent:
                        item_dom = LiHtmlTagDom("none")
                        parent = node.get_parent()
                        parent.replace_child(node, item_dom)
                        item_dom.append_child(node)
                    within_indent = True
                    
            for child in list(node):
                walk(child, within_indent, par_type)
        walk(dom, False, "none")

        
        # General processing
        # - <hr/> tags should consume the surronding newlines
        #     (it will supply them)
        # - </li> consumes preceding newline
        # - bullet tags and their contents should be removed
        #
        # TODO: could combine style tags that have only child (another style)
        # walk dom in preorder traversal
        last_leaf = [None]
        def walk(node):
            if isinstance(node, TagDom):
                # remove bullet tags and their contents
                if isinstance(node.tag, RichTextBulletTag):
                    node.remove()
                    return
                    

            # delete preceding newline of <hr/>
            if isinstance(node, AnchorDom) and \
               isinstance(node.anchor, RichTextHorizontalRule) and \
               isinstance(last_leaf[0], TextDom) and \
               last_leaf[0].text.endswith("\n"):
                last_leaf[0].text = last_leaf[0].text[:-1]

            # delete preceding newline of <ol> <ul>
            if isinstance(node, TagDom) and \
               isinstance(node.tag, RichTextIndentTag) and \
               isinstance(last_leaf[0], TextDom) and \
               last_leaf[0].text.endswith("\n"):
                last_leaf[0].text = last_leaf[0].text[:-1]
                
            # delete preceding newline of </li>
            if isinstance(node, LiHtmlTagDom):

                # get right most descendant
                child = node.last_child()
                while child and not child.is_leaf():
                    if isinstance(child, TagDom) and \
                       isinstance(child.tag, RichTextIndentTag):
                        # let the next li consume newline
                        child = None
                    else:
                        child = child.last_child()
                
                if isinstance(child, TextDom) and \
                   child.text.endswith("\n"):
                    child.text = child.text[:-1]
            
            if node.is_leaf():
                # process leaves
                
                # delete succeeding newline of <hr/>
                if isinstance(last_leaf[0], AnchorDom) and \
                   isinstance(last_leaf[0].anchor, RichTextHorizontalRule) and \
                   isinstance(node, TextDom) and \
                   node.text.startswith("\n"):
                    node.text = node.text[1:]

                # empty tags are skiped as leaves
                if not isinstance(node, TagDom):
                    # record leaf
                    last_leaf[0] = node
                
            else:
                # recurse
                for child in list(node):
                    walk(child)

            # remove empty tags
            if isinstance(node, TagDom) and node.is_leaf():
                node.remove()
                
        walk(dom)

                    

    def write_dom(self, dom):
        """Write DOM"""
        for child in dom:
            if isinstance(child, TextDom):
                self.write_text(child.text)

            elif isinstance(child, TagDom):                
                self.write_tag_begin(child)
                self.write_dom(child)
                self.write_tag_end(child)
            
            elif isinstance(child, AnchorDom):
                self.write_anchor(child.anchor)

            else:
                raise Exception("unknown dom '%s'" % str(dom))


    def write_text(self, text):
        """Write text"""
        
        # TODO: could try to speed this up
        text = text.replace("&", "&amp;")
        text = text.replace(">", "&gt;")
        text = text.replace("<", "&lt;")
        text = text.replace("\t", "&#09;")
        text = text.replace("  ", " &nbsp;")
        text = text.replace("\n", "<br/>\n")
        self._out.write(text)

    def write_anchor(self, anchor):
        """Write an anchor object"""
        
        if isinstance(anchor, RichTextImage):
            # write image
            size_str = ""
            size = anchor.get_size()
                        
            if size[0] is not None:
                size_str += " width=\"%d\"" % size[0]
            if size[1] is not None:
                size_str += " height=\"%d\"" % size[1]
                        
            self._out.write("<img src=\"%s\"%s />" % 
                            (anchor.get_filename(), size_str))

        elif isinstance(anchor, RichTextHorizontalRule):
            # write horizontal rule
            self._out.write("<hr/>")
                    
        else:
            # warning
            #TODO:
            print "unknown anchor element", anchor

    
    def write_tag_begin(self, dom):
        """Write opening tag of DOM"""
        
        tag = dom.tag
        tagname = tag.get_property("name")

        
        if tagname in IGNORE_TAGS:
            pass
        
        elif tagname in self._buffer_tag2html:
            self._out.write("<%s>" % self._buffer_tag2html[tagname])
                    
        elif isinstance(tag, RichTextSizeTag):
            self._out.write('<span style="font-size: %dpt">' % 
                            tag.get_size())

        elif isinstance(tag, RichTextJustifyTag):
            if tagname == "fill":
                text = "justify"
            else:
                text = tagname
            self._out.write('<div style="text-align: %s">' % text)
                
        elif isinstance(tag, RichTextFamilyTag):
            self._out.write('<span style="font-family: %s">' % 
                            tag.get_family())

        elif isinstance(tag, RichTextFGColorTag):
            self._out.write('<span style="color: %s">' % 
                            tagcolor_to_html(
                                tag.get_color()))

        elif isinstance(tag, RichTextBGColorTag):
            self._out.write('<span style="background-color: %s">' % 
                            tagcolor_to_html(
                                tag.get_color()))

        elif isinstance(tag, RichTextIndentTag):
            self._out.write("<ol>")

        elif isinstance(dom, LiHtmlTagDom):
            if dom.kind == "bullet":
                self._out.write('<li style="list-style-type: disc">')
            else:
                # kind == "none"
                self._out.write('<li style="list-style-type: none">')

        else:
            raise HtmlError("unknown tag '%s'" % tag.get_property("name"))
                
        
    def write_tag_end(self, dom):
        """Write closing tag of DOM"""
        
        tag = dom.tag
        tagname = tag.get_property("name")
        
        if tagname in self._buffer_tag2html:
            self._out.write("</%s>" % self._buffer_tag2html[tagname])
                            
        elif tagname in self._justify:
            self._out.write("</div>")

        elif isinstance(tag, RichTextIndentTag):
            self._out.write("</ol>\n")
            
        elif isinstance(dom, LiHtmlTagDom):
            self._out.write("</li>\n")

        elif isinstance(tag, RichTextBulletTag):
            pass
        
        else:
            self._out.write("</span>")


def tagcolor_to_html(c):
    assert len(c) == 13
    return c[0] + c[1] + c[2] + c[5] + c[6] + c[9] + c[10]
    


