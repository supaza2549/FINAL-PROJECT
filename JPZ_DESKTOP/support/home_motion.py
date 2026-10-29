"""อ่านแนวเส้นจากภาพครั้งเดียว แล้วเลื่อนแสงด้วยพิกัดโดยไม่ย่อภาพทุกเฟรม"""
from bisect import bisect_left
from math import hypot,sin,cos,pi,tau

def trace_curve(image,origin=(42,420)):
    pixels=image.load();points=[];distances=[];distance=0.0
    for x in range(image.width):
        weight=0;weighted_y=0
        for y in range(image.height):
            red,green,blue,alpha=pixels[x,y]
            if alpha>=40 and max(red,green,blue)<100:
                weight+=alpha;weighted_y+=y*alpha
        if not weight:continue
        point=(origin[0]+x,origin[1]+weighted_y/weight)
        if points:distance+=hypot(point[0]-points[-1][0],point[1]-points[-1][1])
        points.append(point);distances.append(distance)
    return points,distances

def position(path,distance):
    points,distances=path
    if not points:return None
    if distance<=0:return points[0]
    if distance>=distances[-1]:return points[-1]
    index=bisect_left(distances,distance)
    fraction=(distance-distances[index-1])/(distances[index]-distances[index-1])
    left,right=points[index-1],points[index]
    return left[0]+(right[0]-left[0])*fraction,left[1]+(right[1]-left[1])*fraction

def segment(path,head,length=28):
    points,distances=path
    if not points or head<=0 or head-length>=distances[-1]:return ()
    start=max(0,head-length);end=min(head,distances[-1])
    result=[position(path,start)]
    for index in range(bisect_left(distances,start),bisect_left(distances,end),4):result.append(points[index])
    result.append(position(path,end))
    return tuple(value for point in result for value in point)

FPS=30
LOOP_SECONDS=17
FRAME_COUNT=FPS*LOOP_SECONDS
SPRITE_ORIGIN=(-22,-57)
SPRITE_SIZE=(46,63)

# J55 | คนหยุดโชว์ยีนส์
def story(elapsed):
    """เดินหกวินาที หยุดโชว์ตรงกลางห้าวินาที แล้วเดินต่ออีกหกวินาที"""
    elapsed=min(LOOP_SECONDS,max(0,elapsed))
    walking=elapsed if elapsed<6 else 6 if elapsed<11 else elapsed-5
    facing=0.0;jeans=0.0
    if 6<=elapsed<=11:
        facing=min(ease((elapsed-6)/.55),ease((11-elapsed)/.55))
        # ยกเสร็จตอน 6.9 วินาที ค้างถึง 9.4 วินาที รวม 2.5 วินาที
        jeans=min(ease((elapsed-6.35)/.55),ease((10.05-elapsed)/.65))
    return walking/12,walking,facing,jeans

def ease(value):
    value=min(1,max(0,value))
    return value**3*(10+value*(-15+6*value))

def foot_pose(elapsed,speed,offset=0):
    """ช่วงลงน้ำหนัก เท้าถอยเท่ากับความเร็วลำตัว ทำให้เท้าบนโลกอยู่นิ่ง"""
    cycle=.9;stance=.62;phase=(elapsed/cycle+offset)%1
    half=speed*cycle*stance/2
    if phase<stance:return half-speed*phase*cycle,0.0,True
    t=(phase-stance)/(1-stance);t2=t*t;t3=t2*t
    tangent=-speed*cycle*(1-stance)
    # ความเร็วปลายช่วงยกเท้าตรงกับช่วงลงน้ำหนัก ลดการกระตุกตอนแตะพื้น
    x=(2*t3-3*t2+1)*(-half)+(t3-2*t2+t)*tangent+(-2*t3+3*t2)*half+(t3-t2)*tangent
    lift=sin(pi*t)**2*4.5
    return x,lift,False

def greeting_pose(elapsed):
    if elapsed<15.1 or elapsed>16.85:return 0.0
    if elapsed<15.5:return ease((elapsed-15.1)/.4)
    if elapsed>16.5:return ease((16.85-elapsed)/.35)
    return 1.0

# J56 | วาดคนและโลโก้ JPZ
def render_frame(elapsed,slope,speed):
    """วาดคนขนาดเล็กที่ความละเอียดสี่เท่าแล้วลดลงครั้งเดียวให้ขอบเนียน"""
    from PIL import Image,ImageDraw,ImageFont
    scale=4;image=Image.new('RGBA',(SPRITE_SIZE[0]*scale,SPRITE_SIZE[1]*scale))
    draw=ImageDraw.Draw(image)
    def xy(values):return [(int(round((values[i]-SPRITE_ORIGIN[0])*scale)),int(round((values[i+1]-SPRITE_ORIGIN[1])*scale))) for i in range(0,len(values),2)]
    def polygon(values,color,outline=None):
        points=xy(values);draw.polygon(points,fill=color)
        if outline:draw.line(points+[points[0]],fill=outline,width=scale,joint='curve')
    def line(values,color,width=1):draw.line(xy(values),fill=color,width=max(1,round(width*scale)),joint='curve')
    def ellipse(values,color):draw.ellipse(xy(values),fill=color)
    progress,walking,facing,jeans=story(elapsed)
    bob=.35*(1-cos(tau*walking/.45))
    front=foot_pose(walking,speed);rear=foot_pose(walking,speed,.5)
    def leg(hip,pose,color,shoe):
        foot,lift,planted=pose;ground=foot*slope-lift
        knee=(hip+foot)/2+lift*.65
        knee_y=-11+bob-lift*.35
        polygon((hip-3,-23+bob,hip+3,-23+bob,knee+3.8,knee_y,foot+2.7,ground-1,foot-2.7,ground-1,knee-3.8,knee_y),color,'#203B4F')
        line((hip+1,-22+bob,knee+1,knee_y,foot+1,ground-2),'#7D98AA',.65)
        # ปลายรองเท้าหันขวาไปทางเดียวกับการเดิน
        polygon((foot-3,ground-2,foot+1.5,ground-2,foot+5,ground,foot+5,ground+1.5,foot-3,ground+1.5),shoe,'#243E55')
    leg(-2,rear,'#223F54','#DEDACF');leg(2,front,'#355E7B','#F8F6F0')
    polygon((-5,-26+bob,6,-26+bob,6,-20+bob,-5,-20+bob),'#355E7B','#203B4F')
    line((-4,-25+bob,-2,-22+bob),'#A1B3BB',.65);line((5,-25+bob,3,-22+bob),'#A1B3BB',.65)
    polygon((-4,-38+bob,0,-41+bob,5,-40+bob,7,-36+bob,5,-26+bob,-4,-26+bob),'#202B33','#16212A')
    line((-3,-37+bob,-7,-31+bob,-4,-25+bob),'#202B33',3.2)
    ellipse((-5,-26+bob,-3,-23+bob),'#BFA68E')
    greeting=greeting_pose(elapsed)
    elbow_x=9+greeting;elbow_y=-30-13*greeting
    hand_x=5+(6+2.3*sin(tau*elapsed*1.5))*greeting;hand_y=-25-26*greeting
    line((6,-37+bob,elbow_x,elbow_y+bob,hand_x,hand_y+bob),'#202B33',3.2)
    ellipse((hand_x-1.2,hand_y-1+bob,hand_x+1.2,hand_y+2+bob),'#BFA68E')
    ellipse((0,-49+bob,7,-41+bob),'#BFA68E')
    polygon((6,-46+bob,8,-45+bob,6,-44+bob),'#BFA68E')
    # ผมอยู่ด้านหลังศีรษะ เปิดแก้ม ตา และจมูกทางขวาให้ตรงกับปลายรองเท้า
    polygon((0,-44.5+bob,0,-49+bob,4,-50+bob,6.5,-48+bob,4,-48+bob,4,-46+bob,3,-44.5+bob),'#16212A')
    ellipse((5.1,-46.9+bob,5.9,-46.1+bob),'#16212A')
    if facing:
        side=image.copy();image=Image.new('RGBA',image.size);draw=ImageDraw.Draw(image)
        # หน้าตรง เท้าหยุดนิ่ง และมือทั้งสองยกกางเกงจริงในภาพเคลื่อนไหว
        for x in (-4.5,4.5):
            # เมื่อถอดยีนส์ จะเห็นกางเกงขาสั้นสุภาพและช่วงขาด้านล่าง
            calf=tuple(round(a+(b-a)*jeans) for a,b in zip((53,94,123),(191,166,142)))
            polygon((x-2.5,-23,x+2.5,-23,x+2.7,-1,x-2.7,-1),calf,'#203B4F')
            if jeans>0:
                polygon((x-3,-23,x+3,-23,x+3,-13,x-3,-13),'#D6C6A9','#877354')
            polygon((x-3,-2,x+3,-2,x+3.5,1,x-3.5,1),'#F8F6F0','#243E55')
        polygon((-7,-37,-4,-41,4,-41,7,-37,6,-23,-6,-23),'#202B33','#16212A')
        ellipse((-4,-50,4,-41),'#BFA68E')
        polygon((-4,-45,-4,-49,-1,-51,3,-50,4,-46,1,-48,-1,-47),'#16212A')
        ellipse((-2.5,-46.8,-1.5,-45.8),'#16212A');ellipse((1.5,-46.8,2.5,-45.8),'#16212A')
        line((-1,-43,1,-43),'#8C6A55',.6)
        waist=-23-8*jeans;width=2+10*jeans;bottom=waist+23*jeans
        if jeans>0:
            polygon((-width,waist,width,waist,width-1,bottom,2,bottom,0,waist+10*jeans,-2,bottom,-width+1,bottom),'#497B9D','#203B4F')
            line((-width,waist+2,width,waist+2),'#C4B080',.6)
            line((-width+3,waist+4,-width+5,waist+7),'#C4B080',.6)
            line((width-3,waist+4,width-5,waist+7),'#C4B080',.6)
            if jeans>.7:
                try:font=ImageFont.truetype('arialbd.ttf',6*scale)
                except OSError:font=ImageFont.load_default(size=6*scale)
                # พื้นป้ายเข้มและตัวอักษรหนาช่วยให้อ่านแบรนด์ได้ในภาพขนาดเล็ก
                polygon((-7,waist+3.5,7,waist+3.5,7,waist+10.5,-7,waist+10.5),'#183246')
                draw.text(xy((0,waist+4))[0],'JPZ',font=font,fill='#FFF9EC',anchor='mt',stroke_width=0)
        for sign in (-1,1):
            hand_x=sign*(5+7*jeans);hand_y=-25-6*jeans
            line((sign*6,-37,sign*10,-31,hand_x,hand_y),'#202B33',3.2)
            ellipse((hand_x-1.4,hand_y-1.4,hand_x+1.4,hand_y+1.4),'#BFA68E')
        image=Image.blend(side,image,facing)
    # ขยายเฉพาะตอนโชว์ แล้วคืนขนาดเดิมด้วยจังหวะเดียวกับการยก/เก็บยีนส์
    zoom=1+.7*jeans
    image=image.resize(tuple(round(side*zoom) for side in SPRITE_SIZE),Image.Resampling.LANCZOS)
    alpha=ease(min(elapsed/.3,(LOOP_SECONDS-elapsed)/.3))
    if alpha<1:image.putalpha(image.getchannel('A').point(lambda value:round(value*alpha)))
    return image

def build_frames(path):
    length=path[1][-1];speed=length/12;frames=[]
    for index in range(FRAME_COUNT):
        elapsed=index/FPS;distance=story(elapsed)[0]*length
        left=position(path,distance-4);right=position(path,distance+4)
        slope=(right[1]-left[1])/max(.1,right[0]-left[0])
        frames.append(render_frame(elapsed,slope,speed))
    return frames

def create_walker(canvas):
    item=canvas.create_image(0,0,anchor='nw',state='hidden',tags='home_motion')
    return {'items':{'sprite':item},'images':[],'visible':False,'distance':0.0,'greeting':0.0,'preparing':False,'cache_builds':0,'frame_index':None}

def prepare_walker(app,canvas,walker,path):
    """เตรียมภาพเบื้องหลัง แล้วทยอยสร้างภาพ Tk เพื่อไม่บล็อกหน้าร้าน"""
    from support import image_jobs
    from PIL import ImageTk
    from time import perf_counter
    if walker['preparing'] or walker['images'] or not path[0]:return
    walker['preparing']=True
    def accept(frames):
        if frames is None:walker['preparing']=False;return
        iterator=iter(frames);walker['cache_builds']+=1
        def batch():
            if not image_jobs.is_current(canvas) or not canvas.winfo_exists():return
            started=perf_counter()
            for _ in range(8):
                try:frame=next(iterator)
                except StopIteration:walker['preparing']=False;return
                walker['images'].append(ImageTk.PhotoImage(frame,master=app))
                if perf_counter()-started>.003:break
            app.after(8,batch)
        batch()
    image_jobs.submit(app,canvas,lambda:build_frames(path),accept)

# J12 | คนใส่ยีนส์เดินและโบกมือบนเส้น
def move_walker(canvas,walker,path,distance,phase):
    """เลือกเฟรมที่เตรียมไว้กับเวลาจริง ไม่วาดภาพใหม่ในจังหวะเดิน"""
    if not walker['images']:return
    progress=min(.999999,max(0,distance/max(1,path[1][-1])))
    elapsed=progress*LOOP_SECONDS
    center=position(path,story(elapsed)[0]*path[1][-1])
    if center is None:return
    wanted=int(progress*FRAME_COUNT);index=min(wanted,len(walker['images'])-1)
    item=walker['items']['sprite']
    if index!=walker['frame_index']:
        canvas.itemconfigure(item,image=walker['images'][index]);walker['frame_index']=index
    zoom=1+.7*story(elapsed)[3]
    canvas.coords(item,center[0]+SPRITE_ORIGIN[0]*zoom,center[1]+SPRITE_ORIGIN[1]*zoom)
    if not walker['visible']:canvas.itemconfigure(item,state='normal');walker['visible']=True
    walker['distance']=story(elapsed)[0]*path[1][-1];walker['greeting']=greeting_pose(elapsed)
    walker['showing_jeans']=story(elapsed)[3]

