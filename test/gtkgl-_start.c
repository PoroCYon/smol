#define GL_GLEXT_PROTOTYPES
#include <stdio.h>
#include <stdint.h>

#include <glib.h>
#include <gtk/gtk.h>
#include <gdk/gdkkeysyms.h>

#include <GL/gl.h>

static const char* vshader_vert = "#version 400\nvoid main(){gl_Position=vec4(gl_VertexID%2*2-1,gl_VertexID/2*2-1,1,1);}\n";
static const char* shader_frag = "#version 400\nuniform float v;out vec3 f;vec3 n(vec3 f,vec3 v){vec3 m=cos(v),n=sin(v);return mat3(vec3(m.y*m.z,n.x*n.y*m.z-n.z*m.x,n.x*n.z+m.x*n.y*m.z),vec3(m.y*n.z,n.x*n.y*n.z+m.x*m.z,m.x*n.y*n.z-n.x*m.z),vec3(-n.y,n.x*m.y,m.x*m.y))*f;}float m(vec3 v,vec3 m){vec3 n=abs(v)-m;return length(max(n,0))+min(max(n.x,max(n.y,n.z)),0)-.1;}float x(float v,float m){return min(v,m)-pow(max(1-abs(v-m),0)/2,2);}float m(vec3 f){return x(m(n(f,vec3(1.5,0,0))-vec3(0,0,1.5),vec3(20,20,.01)),m(n(f,vec3(1,v,sin(v*.5)*.5))+vec3(0,.5,0),vec3(.75/2)));}vec3 n(vec3 v){mat3 n=mat3(v,v,v)-mat3(.001);return normalize(m(v)-vec3(m(n[0]),m(n[1]),m(n[2])));}float x(vec3 v){vec3 x=normalize(vec3(1,.5,-.25));float f=1,n=1e20;for(float z=.01;z<10;){float y=m(v+x*z),r;if(y<1e-4)return 0;r=y*y/(2*n);f=min(f,20*sqrt(y*y-r*r)/max(0,z-r));n=y;z+=y;}return f;}void main(){vec2 v=(gl_FragCoord.xy/vec2(1920,1080)*2-1)*vec2(1,.5625);vec3 z=vec3(0,0,-3.5);bool r=false;for(;z.z<20;){float y=m(z);if(y<1e-4){r=true;break;}z+=normalize(vec3(v,1))*y;}float y=length(vec3(0,0,-3.5)-z);if(r){float d=pow(1.-abs(length(z-vec3(1,.5,-.25)))/100,32)*1.5*(dot(n(z),normalize(vec3(1,.5,-.25)))*.5+.5)*.25+pow(max(dot(normalize(vec3(v,1)),reflect(normalize(vec3(1,.5,-.25)),n(z))),0),128)*.9;f=vec3(d)+vec3(.1,.4,.1);f=mix(vec3(0),f,x(vec3(0,0,-3.5)+y*normalize(vec3(v,1)))*.25+.75);}f*=mix(f,vec3(1),1-exp(-.1*pow(y,128)));f-=y*.05;}\n";

static GtkWidget *glarea;

static GLuint sprogram_id;
static GLuint vprogram_id;
static GLuint pipelineId;
static GLuint vao;

static GTimer *timer;

static void on_render() {
	puts("on render");
	glProgramUniform1f(sprogram_id, 0, g_timer_elapsed(timer, NULL));
	gtk_gl_area_queue_render(GTK_GL_AREA(glarea));
	glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);
	glFinish();
}

static void on_realize() {
	puts("onrealize");
	timer = g_timer_new();
	puts("mkcurrent");
	gtk_gl_area_make_current(GTK_GL_AREA(glarea));
	puts("gl genva");
	glGenVertexArrays(1, &vao);
	puts("gl pipeline");
	glGenProgramPipelines(1, &pipelineId);
	puts("gl vertex shader");
	vprogram_id = glCreateShaderProgramv(GL_VERTEX_SHADER, 1, &vshader_vert);
	puts("gl use prgm");
	glUseProgramStages(pipelineId, GL_VERTEX_SHADER_BIT, vprogram_id);
	puts("gl fragment shader");
	sprogram_id = glCreateShaderProgramv(GL_FRAGMENT_SHADER, 1, &shader_frag);
	puts("gl use prgm");
	glUseProgramStages(pipelineId, GL_FRAGMENT_SHADER_BIT, sprogram_id);
	puts("gl bind pipeline");
	glBindProgramPipeline(pipelineId);
	puts("gl bind vao");
	glBindVertexArray(vao);
	puts("gtk main");
	gtk_main();
}

static void check_escape(GtkWidget *widget, GdkEventKey *event) {
	(void)widget;
	puts("check esc");
	if (event->keyval == GDK_KEY_Escape) {
		asm volatile("int3");
		__builtin_unreachable();
	}
}

__attribute__((__used__, __externally_visible__, __section__(".text._start")))
void _start() {
	puts("gtk init");
	gtk_init(NULL, NULL);
	puts("gtk new wnd");
	GtkWidget *win = gtk_window_new(GTK_WINDOW_TOPLEVEL);
	puts("gtk new area");
	glarea = gtk_gl_area_new();
	puts("gtk add container");
	gtk_container_add((GtkContainer *)win, glarea);
	puts("gtk signals");
	g_signal_connect_object(glarea, "render", (GCallback)on_render, NULL, 0);
	g_signal_connect_object(win, "key_press_event", (GCallback)check_escape, NULL, 0);
	puts("gtk show");
	gtk_widget_show_all(win);
	gtk_window_fullscreen((GtkWindow *)win);
	on_realize();
	__builtin_unreachable();
}
